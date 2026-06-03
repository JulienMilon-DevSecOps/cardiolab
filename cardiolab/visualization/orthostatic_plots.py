"""Visualisation helpers for the orthostatic HRV protocol.

One public function:

* :func:`plot_orthostatic_phases_evolution` — multi-session plot showing
  HRV metrics for the three phases (supine / transition / standing) and
  the key autonomic response deltas, making it possible to read the
  orthostatic test as three parallel resting panels over time.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from cardiolab.labels import lbl

_SUPINE_COLOR = "#2980b9"
_TRANSITION_COLOR = "#e67e22"
_STANDING_COLOR = "#27ae60"
_DELTA_COLOR = "#8e44ad"
_DARK = "#2c3e50"
_GRAY = "#95a5a6"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_phases(r: object) -> tuple:
    """Extract (supine_f, transition_f, standing_f) from either result type."""
    if hasattr(r, "phases"):
        p = r.phases
        return p.supine.features, p.transition.features, p.standing.features
    return r.supine, r.transition_features, r.standing


def _safe(val: float) -> float:
    """Return val, replacing NaN with 0."""
    try:
        import math

        return 0.0 if math.isnan(val) else val
    except (TypeError, ValueError):
        return 0.0


def _default_session_labels(results: list) -> list[str]:
    """Fallback X-axis labels from result.date or 'Session N'."""
    out = []
    for i, r in enumerate(results):
        d = getattr(r, "date", None)
        out.append(str(d) if d else f"Session {i + 1}")
    return out


# ── Public function ───────────────────────────────────────────────────────────


def plot_orthostatic_phases_evolution(
    results: list,
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str = "Orthostatic Test — Phases Evolution",
    figsize: tuple[float, float] = (13, 9),
) -> Figure:
    """Plot HRV metrics for each orthostatic phase across sessions.

    Returns a :class:`~matplotlib.figure.Figure` with four stacked panels,
    all sharing the same x-axis (one tick per session):

    * **RMSSD** — supine (blue), transition (orange), standing (green) on the
      same scale, allowing a direct reading of vagal activity per phase.
    * **Heart Rate** — HR per phase (bpm), same colour convention.
    * **Autonomic response** — hr_response (ΔHR bpm) and delta_rmssd (ΔRMSSD ms)
      as bar/line pair showing the magnitude of the postural shift.
    * **LF/HF autonomic balance** — hf_hr_pct_change and lf_hr_pct_change (%)
      to assess vagal withdrawal and sympathetic activation quality.

    Accepts both :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
    (live protocol output) and
    :class:`~cardiolab.database.repository.OrthostaticRecord` (database
    read-back).

    Args:
        results: List of orthostatic result objects in chronological order.
        session_labels: X-axis session labels. Falls back to ``result.date`` or
            ``"Session N"`` when ``None``.
        labels: Translation dict (:data:`~cardiolab.labels.LABELS_EN` or
            :data:`~cardiolab.labels.LABELS_FR`). Pass ``None`` for no translation.
        title: Figure suptitle.
        figsize: Width × height of the figure in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``results`` is empty or ``session_labels`` length mismatches.

    """
    if not results:
        raise ValueError("results must contain at least one item.")
    n = len(results)
    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )
    session_labels = session_labels or _default_session_labels(results)
    x = np.arange(n)

    # Extract per-session values
    rmssd_sup = np.array([_safe(_get_phases(r)[0].rmssd) for r in results])
    rmssd_tra = np.array([_safe(_get_phases(r)[1].rmssd) for r in results])
    rmssd_sta = np.array([_safe(_get_phases(r)[2].rmssd) for r in results])
    hr_sup = np.array([_safe(_get_phases(r)[0].mean_hr) for r in results])
    hr_tra = np.array([_safe(_get_phases(r)[1].mean_hr) for r in results])
    hr_sta = np.array([_safe(_get_phases(r)[2].mean_hr) for r in results])
    hr_resp = np.array([_safe(r.hr_response) for r in results])
    d_rmssd = np.array([_safe(r.delta_rmssd) for r in results])
    hf_hr_pct = np.array([_safe(r.hf_hr_pct_change) for r in results])
    lf_hr_pct = np.array([_safe(r.lf_hr_pct_change) for r in results])

    mk = dict(marker="o", markersize=5, linewidth=1.8)

    fig, axes = plt.subplots(4, 1, figsize=figsize, sharex=True)
    ax_rmssd, ax_hr, ax_resp, ax_balance = axes

    # ── Panel 1: RMSSD per phase ──────────────────────────────────────────────
    ax_rmssd.plot(
        x,
        rmssd_sup,
        color=_SUPINE_COLOR,
        label=lbl(labels, "_phase_Supine", "Supine"),
        **mk,
    )
    ax_rmssd.plot(
        x,
        rmssd_tra,
        color=_TRANSITION_COLOR,
        label=lbl(labels, "_phase_Transition", "Transition"),
        **mk,
        linestyle="--",
    )
    ax_rmssd.plot(
        x,
        rmssd_sta,
        color=_STANDING_COLOR,
        label=lbl(labels, "_phase_Standing", "Standing"),
        **mk,
    )
    ax_rmssd.set_ylabel(lbl(labels, "rmssd", "RMSSD (ms)"), fontsize=10)
    ax_rmssd.legend(loc="upper right", fontsize=8)
    ax_rmssd.grid(alpha=0.20, linestyle=":")

    # ── Panel 2: Heart Rate per phase ─────────────────────────────────────────
    ax_hr.plot(x, hr_sup, color=_SUPINE_COLOR, **mk)
    ax_hr.plot(x, hr_tra, color=_TRANSITION_COLOR, **mk, linestyle="--")
    ax_hr.plot(x, hr_sta, color=_STANDING_COLOR, **mk)
    ax_hr.set_ylabel(lbl(labels, "mean_hr", "HR (bpm)"), fontsize=10)
    ax_hr.grid(alpha=0.20, linestyle=":")

    # ── Panel 3: Autonomic response magnitude ─────────────────────────────────
    width = 0.35
    ax_resp.bar(
        x - width / 2,
        hr_resp,
        width,
        color=_DARK,
        alpha=0.75,
        label=lbl(labels, "hr_response", "ΔHR (bpm)"),
    )
    ax_resp_r = ax_resp.twinx()
    ax_resp_r.plot(
        x,
        d_rmssd,
        color=_DELTA_COLOR,
        linewidth=1.8,
        marker="s",
        markersize=5,
        label=lbl(labels, "delta_rmssd", "ΔRMSSD (ms)"),
    )
    ax_resp.set_ylabel(lbl(labels, "hr_response", "ΔHR (bpm)"), fontsize=10)
    ax_resp_r.set_ylabel(
        lbl(labels, "delta_rmssd", "ΔRMSSD (ms)"), fontsize=10, color=_DELTA_COLOR
    )
    ax_resp_r.tick_params(axis="y", colors=_DELTA_COLOR)
    lines1, lbl1 = ax_resp.get_legend_handles_labels()
    lines2, lbl2 = ax_resp_r.get_legend_handles_labels()
    ax_resp.legend(lines1 + lines2, lbl1 + lbl2, loc="upper right", fontsize=8)
    ax_resp.grid(alpha=0.20, linestyle=":")

    # ── Panel 4: Autonomic balance (%) ────────────────────────────────────────
    ax_balance.plot(
        x,
        hf_hr_pct,
        color=_SUPINE_COLOR,
        linewidth=1.8,
        marker="o",
        markersize=5,
        label=lbl(labels, "hf_hr_pct_change", "HF/HR Δ (%)"),
    )
    ax_balance.plot(
        x,
        lf_hr_pct,
        color=_STANDING_COLOR,
        linewidth=1.8,
        marker="^",
        markersize=5,
        label=lbl(labels, "lf_hr_pct_change", "LF/HR Δ (%)"),
    )
    ax_balance.axhline(0, color=_GRAY, linewidth=0.8, linestyle="--", alpha=0.6)
    ax_balance.set_ylabel("%", fontsize=10)
    ax_balance.legend(loc="upper right", fontsize=8)
    ax_balance.grid(alpha=0.20, linestyle=":")
    ax_balance.set_xticks(x)
    ax_balance.set_xticklabels(session_labels, rotation=40, ha="right", fontsize=9)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig
