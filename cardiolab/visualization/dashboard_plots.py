"""Synthetic dashboard and mini-protocol plots for HRV overview.

Nine public functions cover two categories:

Global / longitudinal dashboards
    * :func:`plot_session_dashboard`    — 2×3 grid: resting HRV + optional protocols.
    * :func:`plot_longitudinal_heatmap` — sessions × metrics normalized colour heatmap.
    * :func:`plot_readiness_evolution`  — readiness score timeline with rolling band.
    * :func:`plot_score_evolution`      — [0–100] score timeline for any protocol.

Per-protocol mini-dashboards
    * :func:`plot_resting_mini`   — 2×2 resting summary (tachogram, Poincaré, PSD, score).
    * :func:`plot_hrr_mini`       — 1×2 HRR recovery curve + semi-circular HRR1 gauge.
    * :func:`plot_drift_mini`     — 1×2 drift curve + metrics summary panel.
    * :func:`plot_vo2max_mini`    — 1×2 model comparison bars + fitness gauge.
    * :func:`plot_coherence_mini` — 1×2 coherence AR PSD + RR tachogram.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Wedge
from scipy.signal import welch

from cardiolab.features.frequency_domain import _ar_psd, _interpolate
from cardiolab.labels import lbl
from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.protocols.hrr import HRRResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.signals.rr import RRSeries

# ── Shared colour / style constants ──────────────────────────────────────────

_DARK = "#2c3e50"
_GRAY = "#95a5a6"
_BLUE = "#2980b9"
_GREEN = "#27ae60"
_ORANGE = "#e67e22"
_RED = "#e74c3c"

_FS: float = 4.0  # resampling frequency for PSD (Hz)
_NPERSEG: int = 256  # Welch window length

# Frequency band limits (Hz)
_VLF_LO: float = 0.003
_VLF_HI: float = 0.04
_LF_HI: float = 0.15
_HF_HI: float = 0.40

# Spectral band colours
_VLF_COLOR = "#fadbd8"
_LF_COLOR = "#fdebd0"
_HF_COLOR = "#d5f5e3"

# Coherence score bands
_COH_LOW: float = 50.0
_COH_MED: float = 70.0
_COH_HIGH: float = 100.0

# Coherence band colours
_COH_LOW_COLOR = "#fadbd8"
_COH_MED_COLOR = "#fef9e7"
_COH_HIGH_COLOR = "#d5f5e3"

# Drift thresholds (bpm/min)
_DRIFT_NO: float = 0.5
_DRIFT_MILD: float = 1.5
_DRIFT_MOD: float = 3.0
_DRIFT_MAX_AXIS: float = 5.0

# Drift zone colours (absolute drift_rate background)
_DRIFT_BG: dict[str, str] = {
    "no_drift": "#eafaf1",
    "mild": "#fef9e7",
    "moderate": "#fdebd0",
    "strong": "#fdf0ef",
}
_DRIFT_CAT_COLORS: dict[str, str] = {
    "no_drift": _GREEN,
    "mild": _ORANGE,
    "moderate": "#e67e22",
    "strong": _RED,
}

# HRR thresholds (bpm)
_HRR_EXCELLENT: float = 25.0
_HRR_GOOD: float = 20.0
_HRR_NORMAL: float = 12.0

# HRR gauge geometry
_HRR_R_OUTER: float = 1.0
_HRR_R_INNER: float = 0.58
_HRR_R_NEEDLE: float = 0.82
_HRR_R_LABEL: float = 1.22
_HRR_R_TICK_IN: float = 0.54
_HRR_R_TICK_OUT: float = 1.04
_HRR_GAUGE_MAX: float = 40.0

_HRR_ZONES: list[tuple[float, float, str]] = [
    (0.0, _HRR_NORMAL, "#fdf0ef"),
    (_HRR_NORMAL, _HRR_GOOD, "#fdebd0"),
    (_HRR_GOOD, _HRR_EXCELLENT, "#fef9e7"),
    (_HRR_EXCELLENT, _HRR_GAUGE_MAX, "#d5f5e3"),
]

# VO2max ACSM thresholds (mL/kg/min)
_VO2_POOR: float = 28.0
_VO2_FAIR: float = 38.0
_VO2_GOOD: float = 48.0
_VO2_VG: float = 58.0
_VO2_MAX: float = 70.0

_VO2_ZONES: list[tuple[float, float, str]] = [
    (0.0, _VO2_POOR, "#fadbd8"),
    (_VO2_POOR, _VO2_FAIR, "#fdebd0"),
    (_VO2_FAIR, _VO2_GOOD, "#fef9e7"),
    (_VO2_GOOD, _VO2_VG, "#d6eaf8"),
    (_VO2_VG, _VO2_MAX, "#d5f5e3"),
]

_VO2_CAT_COLORS: dict[str, str] = {
    "poor": _RED,
    "fair": _ORANGE,
    "good": "#f39c12",
    "very_good": _BLUE,
    "excellent": _GREEN,
}
_VO2_MODEL_COLORS: dict[str, str] = {
    "Uth": _BLUE,
    "Esco-Flatt": _GREEN,
    "ln-RMSSD": _ORANGE,
}

# Window size for rolling bands (sessions)
_ROLLING_WIN: int = 3

# Heatmap metric labels (display name, higher_is_better)
_HEATMAP_META: list[tuple[str, bool]] = [
    ("RMSSD (ms)", True),
    ("HRV Score", True),
    ("HF_nu (%)", True),
    ("HRR1 (bpm)", True),
    ("VO2max (mL/kg/min)", True),
    ("Drift (bpm/min)", False),
    ("Coherence", True),
]


# ── Public C6 dashboards ──────────────────────────────────────────────────────


def plot_session_dashboard(
    rr: RRSeries,
    features: HRVFeatures,
    rr_recovery: RRSeries | None = None,
    hrr_result: HRRResult | None = None,
    rr_exercise: RRSeries | None = None,
    drift_result: DriftResult | None = None,
    vo2max_result: VO2maxResult | None = None,
    title: str = "Session Dashboard",
    figsize: tuple[float, float] = (16, 9),
) -> Figure:
    """Plot a 2×3 multi-protocol session dashboard.

    The top row always shows resting HRV: tachogram, Poincaré scatter, and
    Welch PSD.  The bottom row shows protocol results when supplied:
    HRR recovery curve (left), cardiac drift curve (centre), and VO2max
    fitness gauge (right).  Panels without data show a labelled placeholder.

    Args:
        rr: Resting :class:`~cardiolab.signals.rr.RRSeries`.
        features: :class:`~cardiolab.protocols.resting.HRVFeatures` from the
            same resting recording.
        rr_recovery: Post-exercise :class:`~cardiolab.signals.rr.RRSeries`
            for the HRR panel (optional).
        hrr_result: :class:`~cardiolab.protocols.hrr.HRRResult` (optional).
        rr_exercise: Exercise :class:`~cardiolab.signals.rr.RRSeries` for the
            drift panel (optional).
        drift_result: :class:`~cardiolab.protocols.cardiac_drift.DriftResult`
            (optional).
        vo2max_result: :class:`~cardiolab.protocols.vo2max.VO2maxResult`
            (optional).
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`
            or ``features`` is not an :class:`~cardiolab.protocols.resting.HRVFeatures`.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if not isinstance(features, HRVFeatures):
        raise TypeError(
            f"features must be an HRVFeatures, got {type(features).__name__}"
        )

    fig, axes = plt.subplots(2, 3, figsize=figsize)

    _draw_tachogram(axes[0, 0], rr, title="Resting Tachogram")
    _draw_poincare(axes[0, 1], rr, features, title="Poincaré")
    _draw_psd_welch(axes[0, 2], rr, title="Welch PSD")

    # Bottom row: optional protocol panels
    if rr_recovery is not None and hrr_result is not None:
        _draw_hrr_curve_ax(axes[1, 0], rr_recovery, hrr_result, title="HRR Curve")
    elif hrr_result is not None:
        _draw_hrr_summary(axes[1, 0], hrr_result, title="HRR Summary")
    else:
        _draw_no_data(axes[1, 0], "No HRR data")

    if rr_exercise is not None and drift_result is not None:
        _draw_drift_curve_ax(
            axes[1, 1], rr_exercise, drift_result, title="Cardiac Drift"
        )
    elif drift_result is not None:
        _draw_drift_summary(axes[1, 1], drift_result, title="Drift Summary")
    else:
        _draw_no_data(axes[1, 1], "No Drift data")

    if vo2max_result is not None:
        _draw_vo2max_gauge_ax(axes[1, 2], vo2max_result, title="VO2max Gauge")
    else:
        _draw_no_data(axes[1, 2], "No VO2max data")

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_longitudinal_heatmap(
    features: list[HRVFeatures],
    hrr_results: list[HRRResult] | None = None,
    drift_results: list[DriftResult] | None = None,
    vo2max_results: list[VO2maxResult] | None = None,
    coherence_results: list[CoherenceResult] | None = None,
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "Longitudinal HRV Heatmap",
    figsize: tuple[float, float] = (14, 8),
) -> Figure:
    """Plot a sessions × metrics normalised colour heatmap.

    Each column represents one HRV metric; each row represents one session.
    Values are normalised to [0, 1] column-wise (1 = best, 0 = worst).
    Missing data (``None`` or ``nan``) appears as a grey cell.

    Args:
        features: List of :class:`~cardiolab.protocols.resting.HRVFeatures` in
            chronological order.
        hrr_results: Optional list of :class:`~cardiolab.protocols.hrr.HRRResult`
            (same length as ``features`` or ``None``).
        drift_results: Optional list of
            :class:`~cardiolab.protocols.cardiac_drift.DriftResult`.
        vo2max_results: Optional list of
            :class:`~cardiolab.protocols.vo2max.VO2maxResult`.
        coherence_results: Optional list of
            :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features`` is not a list or contains non-HRVFeatures.
        ValueError: If ``features`` is empty or a results list length mismatches.

    """
    if not isinstance(features, list):
        raise TypeError(f"features must be a list, got {type(features).__name__}")
    if len(features) == 0:
        raise ValueError("features must contain at least one HRVFeatures.")
    for i, f in enumerate(features):
        if not isinstance(f, HRVFeatures):
            raise TypeError(
                f"features[{i}] must be an HRVFeatures, got {type(f).__name__}"
            )
    n = len(features)
    for name, lst in [
        ("hrr_results", hrr_results),
        ("drift_results", drift_results),
        ("vo2max_results", vo2max_results),
        ("coherence_results", coherence_results),
    ]:
        if lst is not None and len(lst) != n:
            raise ValueError(
                f"{name} length ({len(lst)}) must match features length ({n})"
            )

    if session_labels is None:
        session_labels = [
            str(f.date) if f.date else f"Session {i + 1}"
            for i, f in enumerate(features)
        ]

    # Build metric columns: (values_list, higher_is_better)
    cols_vals: list[list[float]] = []
    cols_meta: list[tuple[str, bool]] = []

    def _col(vals: list[float], label: str, higher_is_better: bool) -> None:
        cols_vals.append(vals)
        cols_meta.append((label, higher_is_better))

    _col([f.rmssd for f in features], "RMSSD\n(ms)", True)
    _col([f.score for f in features], "HRV\nScore", True)
    _col([f.hf_nu for f in features], "HFnu\n(%)", True)

    if hrr_results is not None:
        _col([r.hrr_60 for r in hrr_results], "HRR1\n(bpm)", True)
    if vo2max_results is not None:
        _col([_vo2max_best(r) for r in vo2max_results], "VO2max\n(mL/kg/min)", True)
    if drift_results is not None:
        _col([abs(r.drift_rate) for r in drift_results], "Drift\n(bpm/min)", False)
    if coherence_results is not None:
        _col([r.coherence_score for r in coherence_results], "Coherence\nScore", True)

    n_cols = len(cols_vals)
    data = np.full((n, n_cols), np.nan)
    for ci, col in enumerate(cols_vals):
        for ri, val in enumerate(col):
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                data[ri, ci] = float(val)

    # Normalise each column to [0, 1]: 1 = best
    norm_data = np.full_like(data, np.nan)
    for ci, (_, higher) in enumerate(cols_meta):
        col = data[:, ci]
        valid = col[~np.isnan(col)]
        if len(valid) == 0:
            continue
        lo, hi = np.min(valid), np.max(valid)
        rng = hi - lo
        if rng == 0:
            norm_data[:, ci] = 1.0
        else:
            normalized = (col - lo) / rng
            norm_data[:, ci] = normalized if higher else (1.0 - normalized)

    fig, ax = plt.subplots(figsize=figsize)

    # Draw cells manually to handle NaN as grey
    cmap = plt.cm.RdYlGn
    for ri in range(n):
        for ci in range(n_cols):
            v = norm_data[ri, ci]
            if np.isnan(v):
                color = "#cccccc"
                txt_color = _DARK
            else:
                rgba = cmap(v)
                color = rgba
                # Raw value annotation
                raw = data[ri, ci]
                txt_color = "white" if v < 0.25 or v > 0.75 else _DARK
                ax.text(
                    ci,
                    ri,
                    f"{raw:.1f}",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color=txt_color,
                    fontweight="bold",
                )
            rect = plt.Rectangle(
                (ci - 0.5, ri - 0.5),
                1.0,
                1.0,
                color=color if not np.isnan(norm_data[ri, ci]) else "#cccccc",
                zorder=1,
            )
            ax.add_patch(rect)
            if np.isnan(norm_data[ri, ci]):
                ax.text(
                    ci, ri, "—", ha="center", va="center", fontsize=9, color="#888888"
                )

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels([m[0] for m in cols_meta], fontsize=8)
    ax.set_yticks(range(n))
    ax.set_yticklabels(session_labels, fontsize=8)
    ax.invert_yaxis()
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Metric", fontsize=9, labelpad=8)
    ax.set_ylabel("Session", fontsize=9)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Colour bar
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Normalised (0 = worst, 1 = best)", fontsize=8)
    cbar.set_ticks([0.0, 0.5, 1.0])

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_readiness_evolution(
    features: list[HRVFeatures],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "Readiness Score Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot the readiness (HRV composite score) evolution over sessions.

    Draws the session scores as a line with dots coloured by zone and overlays
    a rolling-average band for trend reading.  Zone backgrounds (0–33 low,
    33–66 moderate, 66–100 good) provide immediate daily readiness context.

    Args:
        features: List of :class:`~cardiolab.protocols.resting.HRVFeatures` in
            chronological order.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``features`` is not a list or contains non-HRVFeatures.
        ValueError: If ``features`` is empty or ``labels`` length mismatches.

    """
    if not isinstance(features, list):
        raise TypeError(f"features must be a list, got {type(features).__name__}")
    if len(features) == 0:
        raise ValueError("features must contain at least one HRVFeatures.")
    for i, f in enumerate(features):
        if not isinstance(f, HRVFeatures):
            raise TypeError(
                f"features[{i}] must be an HRVFeatures, got {type(f).__name__}"
            )
    n = len(features)
    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match features length ({n})"
        )
    if session_labels is None:
        session_labels = [
            str(f.date) if f.date else f"Session {i + 1}"
            for i, f in enumerate(features)
        ]

    scores = np.array([f.score for f in features], dtype=float)
    xs = list(range(n))

    fig, ax = plt.subplots(figsize=figsize)

    # Zone backgrounds
    ax.axhspan(0.0, 33.0, color="#fadbd8", alpha=0.35, zorder=0)
    ax.axhspan(33.0, 66.0, color="#fef9e7", alpha=0.35, zorder=0)
    ax.axhspan(66.0, 100.0, color="#d5f5e3", alpha=0.35, zorder=0)
    ax.axhline(33.0, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)
    ax.axhline(66.0, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    # Rolling average band
    if n >= _ROLLING_WIN:
        kernel = np.ones(_ROLLING_WIN) / _ROLLING_WIN
        rolling = np.convolve(scores, kernel, mode="valid")
        rx = list(range(_ROLLING_WIN - 1, n))
        ax.fill_between(
            rx,
            rolling * 0.90,
            rolling * 1.10,
            color="#aed6f1",
            alpha=0.35,
            zorder=1,
            label=f"{_ROLLING_WIN}-session rolling band",
        )
        ax.plot(
            rx,
            rolling,
            color=_BLUE,
            linewidth=1.2,
            linestyle="--",
            alpha=0.7,
            zorder=2,
            label="Rolling mean",
        )

    # Score line
    ax.plot(xs, scores, color=_DARK, linewidth=1.8, zorder=3, label="Score")

    # Session dots coloured by zone
    for x, s in zip(xs, scores, strict=False):
        if s >= 66.0:
            dot_color = _GREEN
        elif s >= 33.0:
            dot_color = _ORANGE
        else:
            dot_color = _RED
        ax.scatter([x], [s], s=55, color=dot_color, zorder=5)
        ax.text(
            x,
            s + 2.0,
            f"{s:.0f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=dot_color,
        )

    # Right-margin zone labels
    ax.text(n - 0.5, 16.5, lbl(labels, "zone_score_low", "Low"), ha="right", va="center", fontsize=8, color=_GRAY)
    ax.text(n - 0.5, 49.5, lbl(labels, "zone_score_moderate", "Moderate"), ha="right", va="center", fontsize=8, color=_GRAY)
    ax.text(n - 0.5, 83.0, lbl(labels, "zone_score_good", "Good"), ha="right", va="center", fontsize=8, color=_GRAY)

    ax.set_xticks(xs)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0.0, 100.0)
    ax.set_ylabel(lbl(labels, "score", "Readiness Score") + " (0–100)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":", axis="y")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_score_evolution(
    results: list,
    protocol_name: str = "Protocol",
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot the [0–100] performance score evolution for any protocol.

    Generic timeline chart that works with any result type carrying a ``.score``
    attribute (``HRVFeatures``, ``HRRResult``, ``CoherenceResult``,
    ``DriftResult``, ``VO2maxResult``, ``OrthostaticRecord``, …).

    The chart shares the same zone layout as
    :func:`plot_readiness_evolution` (red / orange / green bands at 0–33 /
    33–66 / 66–100) and draws a rolling-average band when at least 5 sessions
    are available.

    Args:
        results: List of protocol-result objects in chronological order. Each
            item must expose a ``.score`` attribute (float, [0–100]) and
            optionally a ``.date`` attribute used for automatic x-axis labels.
        protocol_name: Human-readable protocol name used in the y-axis label
            and default title. Defaults to ``"Protocol"``.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure suptitle. Defaults to
            ``"<protocol_name> — Score Evolution"``.
        figsize: Width × height in inches. Defaults to ``(12, 5)``.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``results`` is empty or ``labels`` length mismatches.

    """
    if len(results) == 0:
        raise ValueError("results must contain at least one item.")
    n = len(results)
    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )
    if session_labels is None:
        session_labels = [
            str(getattr(r, "date", None) or f"Session {i + 1}")
            for i, r in enumerate(results)
        ]
    if title is None:
        title = f"{protocol_name} — Score Evolution"

    scores = np.array([float(getattr(r, "score", 0.0)) for r in results])
    xs = list(range(n))

    fig, ax = plt.subplots(figsize=figsize)

    # Zone backgrounds
    ax.axhspan(0.0, 33.0, color="#fadbd8", alpha=0.35, zorder=0)
    ax.axhspan(33.0, 66.0, color="#fef9e7", alpha=0.35, zorder=0)
    ax.axhspan(66.0, 100.0, color="#d5f5e3", alpha=0.35, zorder=0)
    ax.axhline(33.0, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)
    ax.axhline(66.0, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    # Rolling average band (≥ 5 sessions)
    if n >= _ROLLING_WIN:
        kernel = np.ones(_ROLLING_WIN) / _ROLLING_WIN
        rolling = np.convolve(scores, kernel, mode="valid")
        rx = list(range(_ROLLING_WIN - 1, n))
        ax.fill_between(
            rx,
            rolling * 0.90,
            rolling * 1.10,
            color="#aed6f1",
            alpha=0.35,
            zorder=1,
            label=f"{_ROLLING_WIN}-session rolling band",
        )
        ax.plot(
            rx,
            rolling,
            color=_BLUE,
            linewidth=1.2,
            linestyle="--",
            alpha=0.7,
            zorder=2,
            label="Rolling mean",
        )

    # Score line
    ax.plot(xs, scores, color=_DARK, linewidth=1.8, zorder=3, label="Score")

    # Session dots coloured by zone
    for x, s in zip(xs, scores, strict=False):
        dot_color = _GREEN if s >= 66.0 else (_ORANGE if s >= 33.0 else _RED)
        ax.scatter([x], [s], s=55, color=dot_color, zorder=5)
        ax.text(
            x,
            min(s + 2.0, 97.0),
            f"{s:.0f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color=dot_color,
        )

    # Right-margin zone labels
    ax.text(n - 0.5, 16.5, lbl(labels, "zone_score_low", "Low"), ha="right", va="center", fontsize=8, color=_GRAY)
    ax.text(n - 0.5, 49.5, lbl(labels, "zone_score_moderate", "Moderate"), ha="right", va="center", fontsize=8, color=_GRAY)
    ax.text(n - 0.5, 83.0, lbl(labels, "zone_score_good", "Good"), ha="right", va="center", fontsize=8, color=_GRAY)

    ax.set_xticks(xs)
    ax.set_xticklabels(session_labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0.0, 100.0)
    ax.set_ylabel(f"{protocol_name} Score (0–100)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":", axis="y")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


# ── Per-protocol mini-dashboards ─────────────────────────────────────────────


def plot_resting_mini(
    rr: RRSeries,
    features: HRVFeatures,
    title: str = "Resting HRV — Session Summary",
    figsize: tuple[float, float] = (14, 8),
) -> Figure:
    """Plot a 2×2 resting-protocol mini-dashboard.

    Panels: tachogram (top-left), Poincaré scatter (top-right), Welch PSD
    (bottom-left), score + key stats panel (bottom-right).

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries`.
        features: :class:`~cardiolab.protocols.resting.HRVFeatures` from the
            same recording.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``features`` have unexpected types.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if not isinstance(features, HRVFeatures):
        raise TypeError(
            f"features must be an HRVFeatures, got {type(features).__name__}"
        )

    fig, axes = plt.subplots(2, 2, figsize=figsize)
    _draw_tachogram(axes[0, 0], rr, title="HR Tachogram")
    _draw_poincare(axes[0, 1], rr, features, title="Poincaré Scatter")
    _draw_psd_welch(axes[1, 0], rr, title="Welch PSD")
    _draw_resting_stats(axes[1, 1], features, title="Session Stats")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_hrr_mini(
    rr: RRSeries,
    result: HRRResult,
    title: str = "Heart Rate Recovery — Summary",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot a 1×2 HRR mini-dashboard: recovery curve and HRR1 gauge.

    Args:
        rr: Post-exercise :class:`~cardiolab.signals.rr.RRSeries`.
        result: :class:`~cardiolab.protocols.hrr.HRRResult`.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``result`` have unexpected types.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if not isinstance(result, HRRResult):
        raise TypeError(f"result must be an HRRResult, got {type(result).__name__}")

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_hrr_curve_ax(axes[0], rr, result, title="Recovery Curve")
    _draw_hrr_gauge_ax(axes[1], result, title="HRR1 Gauge")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_drift_mini(
    rr: RRSeries,
    result: DriftResult,
    window_sec: float = 60.0,
    title: str = "Cardiac Drift — Summary",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot a 1×2 drift mini-dashboard: drift curve and metrics summary panel.

    Args:
        rr: Exercise :class:`~cardiolab.signals.rr.RRSeries`.
        result: :class:`~cardiolab.protocols.cardiac_drift.DriftResult`.
        window_sec: Window duration in seconds used by the drift algorithm.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``result`` have unexpected types.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if not isinstance(result, DriftResult):
        raise TypeError(f"result must be a DriftResult, got {type(result).__name__}")

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_drift_curve_ax(
        axes[0], rr, result, window_sec=window_sec, title="Drift Curve"
    )
    _draw_drift_summary(axes[1], result, title="Drift Metrics")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_vo2max_mini(
    result: VO2maxResult,
    title: str = "VO2max — Summary",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot a 1×2 VO2max mini-dashboard: model comparison bars and fitness gauge.

    Args:
        result: :class:`~cardiolab.protocols.vo2max.VO2maxResult`.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``result`` is not a :class:`~cardiolab.protocols.vo2max.VO2maxResult`.

    """
    if not isinstance(result, VO2maxResult):
        raise TypeError(f"result must be a VO2maxResult, got {type(result).__name__}")

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_vo2max_bars_ax(axes[0], result, title="Model Comparison")
    _draw_vo2max_gauge_ax(axes[1], result, title="Fitness Gauge")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_coherence_mini(
    rr: RRSeries,
    result: CoherenceResult,
    title: str = "Cardiac Coherence — Summary",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot a 1×2 coherence mini-dashboard: AR PSD and RR tachogram.

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` from a paced-breathing
            coherence session.
        result: :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`.
        title: Figure suptitle.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` or ``result`` have unexpected types.

    """
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if not isinstance(result, CoherenceResult):
        raise TypeError(
            f"result must be a CoherenceResult, got {type(result).__name__}"
        )

    fig, axes = plt.subplots(1, 2, figsize=figsize)
    _draw_coherence_psd_ax(axes[0], rr, result, title="AR PSD — Coherence")
    _draw_coherence_tachogram_ax(axes[1], rr, result, title="RR Tachogram")

    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


# ── Private drawing helpers ───────────────────────────────────────────────────


def _draw_tachogram(ax: plt.Axes, rr: RRSeries, title: str = "") -> None:
    """Draw a HR-over-time tachogram on ``ax``."""
    vals = rr.intervals
    t_min = np.cumsum(vals) / 60_000.0
    hr = 60_000.0 / vals
    ax.plot(t_min, hr, color=_BLUE, linewidth=0.9, alpha=0.85)
    ax.fill_between(
        t_min,
        hr.mean() - hr.std(),
        hr.mean() + hr.std(),
        color=_BLUE,
        alpha=0.12,
        zorder=0,
    )
    ax.axhline(hr.mean(), color=_DARK, linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_xlabel("Time (min)", fontsize=7)
    ax.set_ylabel("HR (bpm)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.grid(alpha=0.15, linestyle=":")


def _draw_poincare(
    ax: plt.Axes, rr: RRSeries, features: HRVFeatures, title: str = ""
) -> None:
    """Draw a Poincaré scatter with SD1/SD2 annotation on ``ax``."""
    vals = rr.intervals
    xs, ys = vals[:-1], vals[1:]
    ax.scatter(xs, ys, s=4, alpha=0.45, color=_BLUE, zorder=3)

    # Identity line
    lo, hi = vals.min(), vals.max()
    ax.plot([lo, hi], [lo, hi], color=_GRAY, linewidth=0.7, linestyle="--", alpha=0.5)

    ax.set_aspect("equal")
    ax.set_xlabel("RRₙ (ms)", fontsize=7)
    ax.set_ylabel("RRₙ₊₁ (ms)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")

    # SD1/SD2 text
    ax.text(
        0.97,
        0.05,
        f"SD1={features.sd1:.1f}\nSD2={features.sd2:.1f}",
        transform=ax.transAxes,
        fontsize=6.5,
        ha="right",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "alpha": 0.8},
    )


def _draw_psd_welch(ax: plt.Axes, rr: RRSeries, title: str = "") -> None:
    """Draw a Welch PSD with VLF/LF/HF band colouring on ``ax``."""
    vals = rr.intervals
    t_s = np.cumsum(vals) / 1000.0
    t_uniform = np.arange(t_s[0], t_s[-1], 1.0 / _FS)
    rr_interp = np.interp(t_uniform, t_s, vals)
    nperseg = min(_NPERSEG, len(rr_interp) // 2)
    if nperseg < 4:
        _draw_no_data(ax, "RR too short for PSD")
        ax.set_title(title, fontsize=8, fontweight="bold")
        return
    freqs, psd = welch(rr_interp, fs=_FS, nperseg=nperseg)
    mask = freqs <= _HF_HI
    ax.semilogy(freqs[mask], psd[mask], color=_BLUE, linewidth=0.9)
    ax.axvspan(_VLF_LO, _VLF_HI, color=_VLF_COLOR, alpha=0.4)
    ax.axvspan(_VLF_HI, _LF_HI, color=_LF_COLOR, alpha=0.4)
    ax.axvspan(_LF_HI, _HF_HI, color=_HF_COLOR, alpha=0.4)
    ax.set_xlim(0.0, _HF_HI)
    ax.set_xlabel("Frequency (Hz)", fontsize=7)
    ax.set_ylabel("PSD (ms²/Hz)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")


def _draw_resting_stats(ax: plt.Axes, features: HRVFeatures, title: str = "") -> None:
    """Draw a key-stats text panel with a score progress bar on ``ax``."""
    ax.axis("off")
    ax.set_title(title, fontsize=8, fontweight="bold")

    score = features.score
    if score >= 66.0:
        score_color = _GREEN
    elif score >= 33.0:
        score_color = _ORANGE
    else:
        score_color = _RED

    # Score bar background
    ax.add_patch(
        plt.Rectangle(
            (0.05, 0.80), 0.90, 0.10, color="#eeeeee", zorder=1, transform=ax.transAxes
        )
    )
    ax.add_patch(
        plt.Rectangle(
            (0.05, 0.80),
            0.90 * score / 100.0,
            0.10,
            color=score_color,
            alpha=0.80,
            zorder=2,
            transform=ax.transAxes,
        )
    )
    ax.text(
        0.50,
        0.855,
        f"Score: {score:.0f} / 100",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=9,
        fontweight="bold",
        color="white",
        zorder=3,
    )

    # Key metrics table
    stats = [
        ("RMSSD", f"{features.rmssd:.1f} ms"),
        ("SDNN", f"{features.sdnn:.1f} ms"),
        ("Mean HR", f"{features.mean_hr:.0f} bpm"),
        ("pNN50", f"{features.pnn50:.1f} %"),
        ("LF/HF", f"{features.lf_hf:.2f}"),
        ("DFA α1", f"{features.dfa_alpha1:.2f}"),
    ]
    y_start = 0.68
    for label, value in stats:
        ax.text(
            0.10,
            y_start,
            label,
            transform=ax.transAxes,
            fontsize=8,
            color=_DARK,
            ha="left",
        )
        ax.text(
            0.90,
            y_start,
            value,
            transform=ax.transAxes,
            fontsize=8,
            color=_BLUE,
            ha="right",
            fontweight="bold",
        )
        y_start -= 0.09


def _draw_hrr_curve_ax(
    ax: plt.Axes, rr: RRSeries, result: HRRResult, title: str = ""
) -> None:
    """Draw an HR recovery curve with HRR1/HRR2 markers on ``ax``."""
    vals = rr.intervals
    t_s = np.cumsum(vals) / 1000.0
    t_uniform = np.arange(t_s[0], t_s[-1], 1.0 / _FS)
    hr_interp = 60.0 / (np.interp(t_uniform, t_s, vals) / 1000.0)

    peak_idx = int(np.argmax(hr_interp))
    hr_from_peak = hr_interp[peak_idx:]
    t_from_peak = (np.arange(len(hr_from_peak)) / _FS) / 60.0  # minutes

    ax.plot(t_from_peak, hr_from_peak, color=_RED, linewidth=1.0, alpha=0.85)
    ax.axhline(hr_from_peak[0], color=_GRAY, linewidth=0.6, linestyle=":", alpha=0.7)

    # HRR1 marker
    idx_60 = min(int(60 * _FS), len(hr_from_peak) - 1)
    ax.annotate(
        f"HRR1={result.hrr_60:.0f} bpm",
        xy=(t_from_peak[idx_60], hr_from_peak[idx_60]),
        xytext=(t_from_peak[idx_60] + 0.05, hr_from_peak[idx_60] + 3),
        fontsize=6.5,
        arrowprops={"arrowstyle": "->", "color": _DARK, "lw": 0.8},
        color=_DARK,
    )

    ax.set_xlabel("Time from peak (min)", fontsize=7)
    ax.set_ylabel("HR (bpm)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.grid(alpha=0.15, linestyle=":")


def _draw_hrr_summary(ax: plt.Axes, result: HRRResult, title: str = "") -> None:
    """Draw a text-based HRR summary panel on ``ax``."""
    ax.axis("off")
    ax.set_title(title, fontsize=8, fontweight="bold")
    stats = [
        ("HRR1 (60 s)", f"{result.hrr_60:.0f} bpm"),
        ("HRR2 (120 s)", f"{result.hrr_120:.0f} bpm"),
        ("Category", result.hrr_60_category.replace("_", " ").title()),
        ("HR peak", f"{result.hr_peak:.0f} bpm"),
        ("HR @ 60 s", f"{result.hr_at_60s:.0f} bpm"),
    ]
    y = 0.75
    for label, val in stats:
        ax.text(0.10, y, label, transform=ax.transAxes, fontsize=9, color=_DARK)
        ax.text(
            0.90,
            y,
            val,
            transform=ax.transAxes,
            fontsize=9,
            color=_BLUE,
            ha="right",
            fontweight="bold",
        )
        y -= 0.13


def _draw_hrr_gauge_ax(ax: plt.Axes, result: HRRResult, title: str = "") -> None:
    """Draw a semi-circular HRR1 gauge on ``ax``."""
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-0.70, 1.35)
    ax.set_title(title, fontsize=8, fontweight="bold")

    gauge_w = _HRR_R_OUTER - _HRR_R_INNER
    for lo, hi, color in _HRR_ZONES:
        t1 = _hrr_angle(hi)
        t2 = _hrr_angle(lo)
        ax.add_patch(
            Wedge((0, 0), _HRR_R_OUTER, t1, t2, width=gauge_w, color=color, zorder=2)
        )
    ax.add_patch(
        Wedge(
            (0, 0),
            _HRR_R_OUTER,
            0,
            180,
            width=gauge_w,
            fill=False,
            edgecolor=_DARK,
            linewidth=0.8,
            zorder=3,
        )
    )

    val = max(0.0, min(result.hrr_60, _HRR_GAUGE_MAX))
    a = math.radians(_hrr_angle(val))
    ax.plot(
        [0, _HRR_R_NEEDLE * math.cos(a)],
        [0, _HRR_R_NEEDLE * math.sin(a)],
        color=_DARK,
        linewidth=1.8,
        solid_capstyle="round",
        zorder=5,
    )
    ax.add_patch(plt.Circle((0, 0), 0.055, color=_DARK, zorder=6))

    cat = result.hrr_60_category.replace("_", " ").title()
    ax.text(
        0,
        -0.20,
        f"{result.hrr_60:.0f}",
        ha="center",
        fontsize=20,
        fontweight="bold",
        color=_DARK,
    )
    ax.text(0, -0.38, "bpm", ha="center", fontsize=8, color=_GRAY)
    ax.text(0, -0.52, cat, ha="center", fontsize=9, fontweight="bold", color=_DARK)


def _draw_drift_curve_ax(
    ax: plt.Axes,
    rr: RRSeries,
    result: DriftResult,
    window_sec: float = 60.0,
    title: str = "",
) -> None:
    """Draw a windowed-HR drift curve with regression line on ``ax``."""
    times_min, hr_per_win = _drift_windows(rr, window_sec)
    if len(times_min) == 0:
        _draw_no_data(ax, "Too few windows")
        ax.set_title(title, fontsize=8, fontweight="bold")
        return

    bg = _DRIFT_BG.get(result.interpretation, "#ffffff")
    ax.set_facecolor(bg)

    ax.scatter(times_min, hr_per_win, s=18, color=_BLUE, zorder=4, alpha=0.85)

    # Regression line anchored at centroid
    t_mean = float(np.mean(times_min))
    hr_mean = float(np.mean(hr_per_win))
    intercept = hr_mean - result.drift_rate * t_mean
    t_line = np.array([times_min[0], times_min[-1]])
    ax.plot(
        t_line,
        result.drift_rate * t_line + intercept,
        color=_RED,
        linewidth=1.2,
        zorder=3,
        alpha=0.9,
    )

    ax.set_xlabel("Time (min)", fontsize=7)
    ax.set_ylabel("HR (bpm)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.text(
        0.97,
        0.05,
        f"Drift: {result.drift_rate:+.2f} bpm/min\nR²={result.r_squared:.2f}",
        transform=ax.transAxes,
        fontsize=6.5,
        ha="right",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "alpha": 0.8},
    )
    ax.grid(alpha=0.15, linestyle=":")


def _draw_drift_summary(ax: plt.Axes, result: DriftResult, title: str = "") -> None:
    """Draw a text-based drift metrics summary panel on ``ax``."""
    ax.axis("off")
    ax.set_title(title, fontsize=8, fontweight="bold")
    cat_color = _DRIFT_CAT_COLORS.get(result.interpretation, _DARK)
    ax.text(
        0.50,
        0.88,
        result.interpretation.replace("_", " ").title(),
        transform=ax.transAxes,
        ha="center",
        fontsize=13,
        fontweight="bold",
        color=cat_color,
    )
    stats = [
        ("Drift rate", f"{result.drift_rate:+.2f} bpm/min"),
        ("Magnitude", f"{result.drift_magnitude:.1f} bpm"),
        ("R²", f"{result.r_squared:.2f}"),
        ("Init HR", f"{result.initial_hr:.0f} bpm"),
        ("Final HR", f"{result.final_hr:.0f} bpm"),
        ("Windows", str(result.n_windows)),
    ]
    y = 0.70
    for label, val in stats:
        ax.text(0.10, y, label, transform=ax.transAxes, fontsize=8.5, color=_DARK)
        ax.text(
            0.90,
            y,
            val,
            transform=ax.transAxes,
            fontsize=8.5,
            color=_BLUE,
            ha="right",
            fontweight="bold",
        )
        y -= 0.10


def _draw_vo2max_bars_ax(ax: plt.Axes, result: VO2maxResult, title: str = "") -> None:
    """Draw grouped VO2max model comparison bars on ``ax``."""
    models: list[tuple[str, float]] = []
    if not math.isnan(result.vo2max_uth):
        models.append(("Uth", result.vo2max_uth))
    models.append(("Esco-Flatt", result.vo2max_esco_flatt))
    models.append(("ln-RMSSD", result.vo2max_ln_rmssd))

    vals = [m[1] for m in models]
    colors = [_VO2_MODEL_COLORS[m[0]] for m in models]
    y_max = max(_VO2_MAX, max(vals) * 1.12)

    for lo, hi, col in _VO2_ZONES:
        ax.axhspan(lo, min(hi, y_max), color=col, alpha=0.35, zorder=0)

    xs = list(range(len(models)))
    ax.bar(xs, vals, color=colors, width=0.5, zorder=4, alpha=0.85)
    for x, val, col in zip(xs, vals, colors, strict=False):
        ax.text(
            x,
            val + y_max * 0.015,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=7,
            fontweight="bold",
            color=col,
        )

    ax.set_xticks(xs)
    ax.set_xticklabels([m[0] for m in models], fontsize=7)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel("VO2max (mL/kg/min)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.grid(alpha=0.15, linestyle=":", axis="y")


def _draw_vo2max_gauge_ax(ax: plt.Axes, result: VO2maxResult, title: str = "") -> None:
    """Draw a semi-circular VO2max fitness gauge on ``ax``."""
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-0.70, 1.35)
    ax.set_title(title, fontsize=8, fontweight="bold")

    gauge_w = _HRR_R_OUTER - _HRR_R_INNER
    for lo, hi, color in _VO2_ZONES:
        t1 = _vo2max_angle(hi)
        t2 = _vo2max_angle(lo)
        ax.add_patch(
            Wedge((0, 0), _HRR_R_OUTER, t1, t2, width=gauge_w, color=color, zorder=2)
        )
    ax.add_patch(
        Wedge(
            (0, 0),
            _HRR_R_OUTER,
            0,
            180,
            width=gauge_w,
            fill=False,
            edgecolor=_DARK,
            linewidth=0.8,
            zorder=3,
        )
    )

    best = _vo2max_best(result)
    val = max(0.0, min(best, _VO2_MAX))
    a = math.radians(_vo2max_angle(val))
    ax.plot(
        [0, _HRR_R_NEEDLE * math.cos(a)],
        [0, _HRR_R_NEEDLE * math.sin(a)],
        color=_DARK,
        linewidth=1.8,
        solid_capstyle="round",
        zorder=5,
    )
    ax.add_patch(plt.Circle((0, 0), 0.055, color=_DARK, zorder=6))

    cat = result.fitness_category.replace("_", " ").title()
    cat_color = _VO2_CAT_COLORS.get(result.fitness_category, _DARK)
    ax.text(
        0,
        -0.20,
        f"{best:.0f}",
        ha="center",
        fontsize=20,
        fontweight="bold",
        color=cat_color,
    )
    ax.text(0, -0.38, "mL/kg/min", ha="center", fontsize=7.5, color=_GRAY)
    ax.text(0, -0.52, cat, ha="center", fontsize=9, fontweight="bold", color=cat_color)


def _draw_coherence_psd_ax(
    ax: plt.Axes, rr: RRSeries, result: CoherenceResult, title: str = ""
) -> None:
    """Draw an AR PSD with resonance band highlighted on ``ax``."""
    try:
        _, interp_rr = _interpolate(rr, _FS)
        freqs, psd = _ar_psd(interp_rr, fs=_FS, order=16)
    except Exception:
        _draw_no_data(ax, "PSD unavailable")
        ax.set_title(title, fontsize=8, fontweight="bold")
        return

    mask = freqs <= _HF_HI
    ax.semilogy(freqs[mask], psd[mask], color=_DARK, linewidth=0.9)

    # Resonance band ±0.02 Hz around resonance_freq
    res_f = result.resonance_freq
    bw = 0.02
    ax.axvspan(
        max(0.0, res_f - bw),
        res_f + bw,
        color="#aed6f1",
        alpha=0.55,
        zorder=0,
        label=f"{res_f:.3f} Hz",
    )
    ax.axvline(res_f, color=_BLUE, linewidth=0.9, linestyle="--", alpha=0.8)

    ax.set_xlim(0.0, _HF_HI)
    ax.set_xlabel("Frequency (Hz)", fontsize=7)
    ax.set_ylabel("PSD (ms²/Hz)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.text(
        0.97,
        0.97,
        f"Score: {result.coherence_score:.1f}",
        transform=ax.transAxes,
        fontsize=7,
        ha="right",
        va="top",
        bbox={"boxstyle": "round,pad=0.3", "fc": "white", "alpha": 0.8},
    )


def _draw_coherence_tachogram_ax(
    ax: plt.Axes, rr: RRSeries, result: CoherenceResult, title: str = ""
) -> None:
    """Draw an RR tachogram with sinusoidal respiratory reference on ``ax``."""
    vals = rr.intervals
    t_s = np.cumsum(vals) / 1000.0
    mean_rr = float(np.mean(vals))
    amplitude = float(np.std(vals))

    ax.plot(t_s, vals, color=_DARK, linewidth=0.9, alpha=0.85, label="RR intervals")

    # Sinusoidal reference at resonance frequency
    t_ref = np.linspace(t_s[0], t_s[-1], 500)
    phase = 2.0 * math.pi * result.resonance_freq * t_ref
    ref = mean_rr + amplitude * np.sin(phase)
    ax.plot(
        t_ref,
        ref,
        color=_BLUE,
        linewidth=0.8,
        linestyle="--",
        alpha=0.6,
        label=f"{result.resonance_freq:.3f} Hz ref",
    )

    ax.set_xlabel("Time (s)", fontsize=7)
    ax.set_ylabel("RR (ms)", fontsize=7)
    ax.tick_params(labelsize=6)
    ax.set_title(title, fontsize=8, fontweight="bold")
    ax.legend(fontsize=6, loc="upper right")


def _draw_no_data(ax: plt.Axes, label: str = "No data") -> None:
    """Draw a placeholder panel with a centred label on ``ax``."""
    ax.set_facecolor("#f8f9fa")
    ax.text(
        0.5,
        0.5,
        label,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=10,
        color=_GRAY,
        fontstyle="italic",
    )
    for spine in ax.spines.values():
        spine.set_edgecolor("#dddddd")
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)


# ── Private utility functions ─────────────────────────────────────────────────


def _hrr_angle(value: float) -> float:
    """Convert an HRR1 value (bpm) to a gauge angle (0–180°)."""
    clamped = max(0.0, min(value, _HRR_GAUGE_MAX))
    return 180.0 - (clamped / _HRR_GAUGE_MAX) * 180.0


def _vo2max_angle(value: float) -> float:
    """Convert a VO2max value (mL/kg/min) to a gauge angle (0–180°)."""
    clamped = max(0.0, min(value, _VO2_MAX))
    return 180.0 - (clamped / _VO2_MAX) * 180.0


def _vo2max_best(result: VO2maxResult) -> float:
    """Return the best VO2max estimate: Uth if available, else ln-RMSSD."""
    if not math.isnan(result.vo2max_uth):
        return result.vo2max_uth
    return result.vo2max_ln_rmssd


def _drift_windows(rr: RRSeries, window_sec: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (times_min, hr_per_window) arrays from non-overlapping windows."""
    vals = rr.intervals
    window_ms = window_sec * 1000.0
    cumsum = np.cumsum(vals)
    times, hrs = [], []
    win_start_ms = 0.0

    for elapsed in cumsum:
        if elapsed - win_start_ms >= window_ms:
            end_ms = elapsed
            mask = (cumsum >= win_start_ms) & (cumsum < end_ms)
            win_rr = vals[mask]
            if len(win_rr) > 0:
                times.append((win_start_ms + end_ms) / 2.0 / 60_000.0)
                hrs.append(float(60_000.0 / np.mean(win_rr)))
            win_start_ms = elapsed

    return np.array(times), np.array(hrs)
