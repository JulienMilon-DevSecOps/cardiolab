"""Visualisation helpers for cardiac coherence (cohérence cardiaque).

Three public functions cover the coherence domain:

* :func:`plot_coherence_psd`              — AR PSD with resonance band and annotated peak.
* :func:`plot_coherence_score_evolution`  — Coherence score evolution over sessions.
* :func:`plot_coherence_tachogram`        — RR tachogram with sinusoidal respiratory reference.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.features.frequency_domain import _ar_psd, _interpolate
from cardiolab.labels import lbl
from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.signals.rr import RRSeries

# ── Band and score constants ──────────────────────────────────────────────────

_RESONANCE_LOW = 0.04  # Hz — lower bound of cardiac resonance band
_RESONANCE_HIGH = 0.26  # Hz — upper bound of cardiac resonance band
_RESONANCE_TARGET = 0.1  # Hz — expected peak for 6 breaths/min (5-5 pattern)
_SCORE_GOOD = 60  # % — good coherence threshold
_SCORE_MODERATE = 40  # % — moderate / low coherence boundary
_MIN_INTERVALS_PSD = 5  # minimum intervals needed for PSD computation

_AR_FS: float = 4.0  # resampling frequency (Hz), matches cardiac_coherence default
_AR_ORDER: int = 16  # AR model order, matches cardiac_coherence default

# ── Colour palette ────────────────────────────────────────────────────────────

_RR_COLOR = "#2980b9"
_RESONANCE_FILL = "#d5f5e3"
_RESONANCE_EDGE = "#27ae60"
_PEAK_COLOR = "#e74c3c"
_SINE_COLOR = "#e74c3c"
_SCORE_LINE_COLOR = "#27ae60"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"

# ── Coherence score interpretation bands ─────────────────────────────────────

_COHERENCE_ZONES = [
    (_SCORE_GOOD, 100, "#d5f5e3", "Good coherence"),
    (_SCORE_MODERATE, _SCORE_GOOD, "#fef9e7", "Moderate coherence"),
    (0, _SCORE_MODERATE, "#fadbd8", "Low coherence"),
]
_COHERENCE_ZONE_KEYS = ["zone_coh_good", "zone_coh_moderate", "zone_coh_low"]


# ── Public functions ──────────────────────────────────────────────────────────


def plot_coherence_psd(
    rr: RRSeries,
    result: CoherenceResult,
    resonance_low: float = _RESONANCE_LOW,
    resonance_high: float = _RESONANCE_HIGH,
    fs: float = _AR_FS,
    order: int = _AR_ORDER,
    title: str = "Cardiac Coherence — AR Power Spectral Density",
    figsize: tuple[float, float] = (10, 5),
) -> Figure:
    """Plot the AR PSD of a cardiac coherence session with resonance band annotation.

    Draws the one-sided AR power spectral density over 0–0.5 Hz.  The cardiac
    resonance band [``resonance_low`` – ``resonance_high``] is filled in light
    green.  When a valid resonance peak is found in the result, a red dashed
    vertical line marks its frequency and an annotation box reports the coherence
    score.

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` from the coherence session.
        result: :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`
            produced by :func:`~cardiolab.protocols.cardiac_coherence.cardiac_coherence`.
        resonance_low: Lower bound of the resonance band (Hz). Defaults to 0.04.
        resonance_high: Upper bound of the resonance band (Hz). Defaults to 0.26.
        fs: Resampling frequency for interpolation (Hz). Defaults to 4.0.
        order: AR model order. Defaults to 16.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`
            or ``result`` is not a :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`.
        ValueError: If ``rr`` has fewer than ``_MIN_INTERVALS_PSD`` intervals.

    """
    _validate_rr(rr)
    _validate_result(result)

    _, interp_rr = _interpolate(rr, fs)
    try:
        freqs, psd = _ar_psd(interp_rr, fs=fs, order=order)
    except Exception:  # noqa: BLE001
        freqs = np.linspace(0, fs / 2, 128)
        psd = np.zeros_like(freqs)

    fig, ax = plt.subplots(figsize=figsize)

    # Full PSD curve (0–0.5 Hz)
    mask_display = freqs <= fs / 2
    ax.plot(
        freqs[mask_display], psd[mask_display], color=_DARK, linewidth=1.4, zorder=3
    )

    # Resonance band — filled
    mask_res = (freqs >= resonance_low) & (freqs <= resonance_high)
    if np.any(mask_res):
        ax.fill_between(
            freqs[mask_res],
            psd[mask_res],
            color=_RESONANCE_FILL,
            alpha=0.7,
            zorder=2,
            label=f"Resonance band\n({resonance_low}–{resonance_high} Hz)",
        )
        ax.plot(
            freqs[mask_res],
            psd[mask_res],
            color=_RESONANCE_EDGE,
            linewidth=1.2,
            zorder=3,
        )

    # Resonance peak annotation
    if result.resonance_freq > 0.0:
        ax.axvline(
            result.resonance_freq,
            color=_PEAK_COLOR,
            linewidth=1.2,
            linestyle="--",
            alpha=0.85,
            zorder=4,
            label=f"Peak: {result.resonance_freq:.3f} Hz",
        )
        ax.annotate(
            f"{result.resonance_freq:.3f} Hz",
            xy=(result.resonance_freq, result.peak_power),
            xytext=(result.resonance_freq + 0.02, result.peak_power * 0.9),
            fontsize=8,
            color=_PEAK_COLOR,
            arrowprops={"arrowstyle": "->", "color": _PEAK_COLOR, "lw": 0.9},
        )

    # Target breathing frequency reference
    ax.axvline(
        _RESONANCE_TARGET,
        color=_GRAY,
        linewidth=0.8,
        linestyle=":",
        alpha=0.6,
        label=f"Target: {_RESONANCE_TARGET} Hz",
    )

    # Coherence score annotation box
    score_color = _score_color(result.coherence_score)
    score_text = (
        f"Coherence score: {result.coherence_score:.1f} %\n"
        f"{_score_label(result.coherence_score)}"
    )
    ax.text(
        0.98,
        0.97,
        score_text,
        transform=ax.transAxes,
        ha="right",
        va="top",
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": score_color,
            "alpha": 0.85,
            "edgecolor": "#bdc3c7",
        },
        fontsize=9,
    )

    ax.set_xlim(0, fs / 2)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Frequency (Hz)", fontsize=10)
    ax.set_ylabel("Power (ms²/Hz)", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_coherence_score_evolution(
    results: list[CoherenceResult],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "Cardiac Coherence Score — Evolution",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot cardiac coherence score evolution over multiple sessions.

    Draws the coherence score as a line with coloured background interpretation
    bands (green ≥ 60 %, yellow 40–60 %, red < 40 %).  Threshold lines at
    40 % and 60 % are drawn for quick reading.  Each point is annotated with
    its numeric score.

    Args:
        results: List of :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`
            in chronological order.
        session_labels: X-axis session labels. Falls back to date attributes
            or ``'Session N'`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``results`` is not a list or contains non-CoherenceResult elements.
        ValueError: If ``results`` is empty.
        ValueError: If ``labels`` length does not match ``results`` length.

    """
    _validate_results_list(results)
    n = len(results)

    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )

    session_labels = session_labels or _default_labels(results)
    x = np.arange(n)
    scores = np.array([r.coherence_score for r in results], dtype=float)

    fig, ax = plt.subplots(figsize=figsize)

    # Coloured interpretation bands
    for low, high, color, _ in _COHERENCE_ZONES:
        ax.axhspan(low, high, color=color, alpha=0.45, zorder=0)
    for threshold in (_SCORE_MODERATE, _SCORE_GOOD):
        ax.axhline(threshold, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    # Score line
    ax.plot(
        x,
        scores,
        color=_SCORE_LINE_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=6,
        zorder=4,
    )

    # Score labels on each point
    for xi, sc in zip(x, scores, strict=False):
        ax.annotate(
            f"{sc:.0f}",
            xy=(xi, sc),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=_DARK,
        )

    ax.set_ylim(0, 105)
    ax.set_ylabel(lbl(labels, "coherence_score", "Coherence score (%)"), fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(session_labels, rotation=40, ha="right", fontsize=9)
    ax.grid(alpha=0.20, linestyle=":", axis="y")

    # Zone legend
    from matplotlib.patches import Patch

    legend_patches = [
        Patch(facecolor=color, alpha=0.6, label=lbl(labels, zone_key, label))
        for (_, _, color, label), zone_key in zip(_COHERENCE_ZONES, _COHERENCE_ZONE_KEYS, strict=True)
    ]
    ax.legend(handles=legend_patches, loc="upper left", fontsize=8)

    fig.suptitle(title, fontsize=13, fontweight="bold", y=1.01)
    plt.tight_layout()
    return fig


def plot_coherence_tachogram(
    rr: RRSeries,
    result: CoherenceResult,
    title: str = "RR Tachogram — Cardiac Coherence Session",
    figsize: tuple[float, float] = (12, 5),
) -> Figure:
    """Plot the RR tachogram with a sinusoidal respiratory reference overlay.

    Superimposes a reference sine wave at the session resonance frequency onto
    the raw RR tachogram.  When the RR oscillations track the reference closely,
    the session shows good cardiac coherence.  Divergence between the two signals
    indicates poor synchronisation between breathing and heart rate.

    The reference amplitude is derived from the session RMSSD:
    ``amplitude = result.rmssd × √2``.

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` from the coherence session.
        result: :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`
            produced by :func:`~cardiolab.protocols.cardiac_coherence.cardiac_coherence`.
        title: Figure title.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        TypeError: If ``rr`` is not an :class:`~cardiolab.signals.rr.RRSeries`
            or ``result`` is not a :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`.
        ValueError: If ``rr`` has fewer than ``_MIN_INTERVALS_PSD`` intervals.

    """
    _validate_rr(rr)
    _validate_result(result)

    intervals = np.array(rr.intervals, dtype=float)
    beat_times = np.cumsum(intervals) / 1000.0  # seconds
    mean_rr = float(np.mean(intervals))

    fig, ax = plt.subplots(figsize=figsize)

    # RR tachogram
    ax.plot(
        beat_times,
        intervals,
        color=_RR_COLOR,
        linewidth=1.4,
        marker="o",
        markersize=3,
        alpha=0.8,
        label="RR intervals",
        zorder=3,
    )
    ax.axhline(
        mean_rr,
        color=_GRAY,
        linewidth=0.8,
        linestyle="--",
        alpha=0.7,
        label=f"Mean RR ({mean_rr:.0f} ms)",
    )

    # Sinusoidal respiratory reference
    if result.resonance_freq > 0.0:
        amplitude = result.rmssd * float(np.sqrt(2))
        t_ref = np.linspace(0.0, float(beat_times[-1]), 1000)
        sine_ref = mean_rr + amplitude * np.sin(
            2.0 * np.pi * result.resonance_freq * t_ref
        )
        ax.plot(
            t_ref,
            sine_ref,
            color=_SINE_COLOR,
            linewidth=1.6,
            linestyle="--",
            alpha=0.75,
            zorder=2,
            label=f"Reference sine ({result.resonance_freq:.3f} Hz)",
        )

        # Shaded ±RMSSD band around mean
        ax.fill_between(
            t_ref,
            mean_rr - result.rmssd,
            mean_rr + result.rmssd,
            color=_RR_COLOR,
            alpha=0.08,
            zorder=1,
        )

    # Coherence score annotation
    score_color = _score_color(result.coherence_score)
    score_text = f"Score: {result.coherence_score:.1f} %\nRMSSD: {result.rmssd:.1f} ms"
    ax.text(
        0.02,
        0.97,
        score_text,
        transform=ax.transAxes,
        va="top",
        bbox={
            "boxstyle": "round,pad=0.4",
            "facecolor": score_color,
            "alpha": 0.85,
            "edgecolor": "#bdc3c7",
        },
        fontsize=9,
    )

    ax.set_xlabel("Time (s)", fontsize=10)
    ax.set_ylabel("RR interval (ms)", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(alpha=0.20, linestyle=":")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    plt.tight_layout()
    return fig


# ── Private helpers ───────────────────────────────────────────────────────────


def _validate_rr(rr: RRSeries) -> None:
    """Raise TypeError or ValueError when rr is not a valid RRSeries."""
    if not isinstance(rr, RRSeries):
        raise TypeError(f"rr must be an RRSeries, got {type(rr).__name__}")
    if len(rr.intervals) < _MIN_INTERVALS_PSD:
        raise ValueError(
            f"rr must have at least {_MIN_INTERVALS_PSD} intervals, "
            f"got {len(rr.intervals)}"
        )


def _validate_result(result: CoherenceResult) -> None:
    """Raise TypeError when result is not a CoherenceResult."""
    if not isinstance(result, CoherenceResult):
        raise TypeError(
            f"result must be a CoherenceResult, got {type(result).__name__}"
        )


def _validate_results_list(results: list[CoherenceResult]) -> None:
    """Raise TypeError or ValueError when results is not a valid list."""
    if not isinstance(results, list):
        raise TypeError(f"results must be a list, got {type(results).__name__}")
    if len(results) == 0:
        raise ValueError("results must contain at least one CoherenceResult.")
    for idx, item in enumerate(results):
        if not isinstance(item, CoherenceResult):
            raise TypeError(
                f"results[{idx}] must be a CoherenceResult, got {type(item).__name__}"
            )


def _default_labels(results: list[CoherenceResult]) -> list[str]:
    """Return date strings from results or fallback 'Session N' labels."""
    return [
        str(r.date) if r.date else f"Session {i + 1}" for i, r in enumerate(results)
    ]


def _score_label(score: float) -> str:
    """Return an interpretation string for a coherence score."""
    if math.isnan(score):
        return "—"
    if score >= _SCORE_GOOD:
        return "Good coherence"
    if score >= _SCORE_MODERATE:
        return "Moderate coherence"
    return "Low coherence"


def _score_color(score: float) -> str:
    """Return the background hex colour for a coherence score annotation box."""
    if math.isnan(score) or score < _SCORE_MODERATE:
        return "#fadbd8"
    if score < _SCORE_GOOD:
        return "#fef9e7"
    return "#d5f5e3"
