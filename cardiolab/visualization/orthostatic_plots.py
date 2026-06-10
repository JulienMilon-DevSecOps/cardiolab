"""Visualisation helpers for the orthostatic HRV protocol.

Two public functions:

* :func:`plot_orthostatic_phases_evolution` — multi-session plot showing
  HRV metrics for the three phases (supine / transition / standing) and
  the key autonomic response deltas, making it possible to read the
  orthostatic test as three parallel resting panels over time.
* :func:`plot_orthostatic_dual_score_evolution` — two-panel score timeline:
  readiness score (supine vs baseline, with rolling mean) and autonomic
  score (ΔHR + HF withdrawal), each with their own zone bands.
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

_ROLLING_WIN: int = 3

_ZONE_RED = "#fadbd8"
_ZONE_ORANGE = "#fdebd0"
_ZONE_YELLOW = "#fef9e7"
_ZONE_LIGHTGREEN = "#eafaf1"
_ZONE_GREEN = "#d5f5e3"


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


# ── Public functions ──────────────────────────────────────────────────────────


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


def plot_orthostatic_dual_score_evolution(
    results: list,
    readiness_scores: list[float],
    session_labels: list[str] | None = None,
    labels: dict[str, str] | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (12, 8),
) -> Figure:
    """Plot readiness_score and autonomic_score evolution for orthostatic sessions.

    Two stacked panels sharing the same x-axis (one tick per session):

    * **Readiness score** (top) — supine phase vs personal supine baseline [0–100],
      neutral at 50. A rolling-mean band is drawn when ≥ 3 sessions are available.
      Zone bands: high fatigue (< 35), slight fatigue (35–45), normal (45–55),
      good recovery (55–65), excellent (≥ 65).
    * **Autonomic score** (bottom) — ΔHR + HF withdrawal composite [0–100].
      Zone bands: impaired (< 30), borderline (30–50), normal (50–70),
      good (70–85), excellent (≥ 85).

    Args:
        results: List of orthostatic result objects in chronological order.
            Each item must expose a ``.score`` attribute (autonomic score).
        readiness_scores: Pre-computed readiness scores, one per session in
            the same order as ``results``.
        session_labels: X-axis labels. Falls back to ``result.date`` or
            ``"Session N"`` when ``None``.
        labels: Translation dict (``LABELS_EN`` or ``LABELS_FR``).
        title: Figure suptitle. Defaults to
            ``"Orthostatic — Score Evolution"``.
        figsize: Width × height in inches.

    Returns:
        The :class:`~matplotlib.figure.Figure`.

    Raises:
        ValueError: If ``results`` is empty or ``readiness_scores`` length
            does not match ``results``.

    """
    if not results:
        raise ValueError("results must contain at least one item.")
    n = len(results)
    if len(readiness_scores) != n:
        raise ValueError(
            f"readiness_scores length ({len(readiness_scores)}) must match results length ({n})"
        )
    if session_labels is not None and len(session_labels) != n:
        raise ValueError(
            f"session_labels length ({len(session_labels)}) must match results length ({n})"
        )
    session_labels = session_labels or _default_session_labels(results)
    if title is None:
        title = lbl(labels, "ortho_dual_score_title", "Orthostatic — Score Evolution")

    xs = list(range(n))
    auto_scores = np.array([float(getattr(r, "score", 0.0)) for r in results])
    read_scores = np.array(readiness_scores, dtype=float)

    mk = dict(marker="o", markersize=5, linewidth=1.8)

    fig, (ax_read, ax_auto) = plt.subplots(2, 1, figsize=figsize, sharex=True)

    # ── Panel 1: Readiness Score (supine vs baseline) ─────────────────────────
    ax_read.axhspan(0.0, 35.0, color=_ZONE_RED, alpha=0.40, zorder=0)
    ax_read.axhspan(35.0, 45.0, color=_ZONE_ORANGE, alpha=0.40, zorder=0)
    ax_read.axhspan(45.0, 55.0, color=_ZONE_YELLOW, alpha=0.40, zorder=0)
    ax_read.axhspan(55.0, 65.0, color=_ZONE_LIGHTGREEN, alpha=0.40, zorder=0)
    ax_read.axhspan(65.0, 100.0, color=_ZONE_GREEN, alpha=0.40, zorder=0)
    for y in (35.0, 45.0, 55.0, 65.0):
        ax_read.axhline(y, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)
    ax_read.axhline(50.0, color=_DARK, linewidth=0.9, linestyle="--", alpha=0.45)

    if n >= _ROLLING_WIN:
        kernel = np.ones(_ROLLING_WIN) / _ROLLING_WIN
        rolling = np.convolve(read_scores, kernel, mode="valid")
        rx = list(range(_ROLLING_WIN - 1, n))
        ax_read.fill_between(
            rx,
            rolling - 5.0,
            rolling + 5.0,
            color="#aed6f1",
            alpha=0.35,
            zorder=1,
            label=f"{_ROLLING_WIN}-session rolling band",
        )
        ax_read.plot(
            rx,
            rolling,
            color=_SUPINE_COLOR,
            linewidth=1.2,
            linestyle="--",
            alpha=0.7,
            zorder=2,
            label="Rolling mean",
        )

    ax_read.plot(
        xs,
        read_scores,
        color=_DARK,
        zorder=3,
        label=lbl(labels, "readiness_score", "Readiness Score"),
        **mk,
    )
    for x, s in zip(xs, read_scores, strict=False):
        if s >= 65.0:
            dot_c = _STANDING_COLOR
        elif s >= 55.0:
            dot_c = "#52be80"
        elif s >= 45.0:
            dot_c = _TRANSITION_COLOR
        else:
            dot_c = "#e74c3c"
        ax_read.scatter([x], [s], s=55, color=dot_c, zorder=5)
        ax_read.text(x, s + 2.5, f"{s:.0f}", ha="center", va="bottom", fontsize=7, color=dot_c)

    ax_read.text(
        n - 0.5, 17.5, lbl(labels, "readiness_label_high_fatigue", "High fatigue"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_read.text(
        n - 0.5, 40.0, lbl(labels, "readiness_label_slight_fatigue", "Slight fatigue"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_read.text(
        n - 0.5, 50.0, lbl(labels, "readiness_label_normal", "Normal"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_read.text(
        n - 0.5, 60.0, lbl(labels, "readiness_label_good_recovery", "Good recovery"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_read.text(
        n - 0.5, 82.5, lbl(labels, "readiness_label_excellent", "Excellent"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_read.set_ylim(0.0, 100.0)
    ax_read.set_ylabel(
        lbl(labels, "readiness_score", "Readiness Score") + " (0–100)", fontsize=10
    )
    ax_read.legend(loc="upper left", fontsize=8)
    ax_read.grid(alpha=0.20, linestyle=":", axis="y")

    # ── Panel 2: Autonomic Score (ΔHR + HF withdrawal) ───────────────────────
    ax_auto.axhspan(0.0, 30.0, color=_ZONE_RED, alpha=0.40, zorder=0)
    ax_auto.axhspan(30.0, 50.0, color=_ZONE_ORANGE, alpha=0.40, zorder=0)
    ax_auto.axhspan(50.0, 70.0, color=_ZONE_YELLOW, alpha=0.40, zorder=0)
    ax_auto.axhspan(70.0, 85.0, color=_ZONE_LIGHTGREEN, alpha=0.40, zorder=0)
    ax_auto.axhspan(85.0, 100.0, color=_ZONE_GREEN, alpha=0.40, zorder=0)
    for y in (30.0, 50.0, 70.0, 85.0):
        ax_auto.axhline(y, color=_GRAY, linewidth=0.7, linestyle=":", alpha=0.8)

    ax_auto.plot(xs, auto_scores, color=_DARK, zorder=3, **mk)
    for x, s in zip(xs, auto_scores, strict=False):
        if s >= 70.0:
            dot_c = _STANDING_COLOR
        elif s >= 30.0:
            dot_c = _TRANSITION_COLOR
        else:
            dot_c = "#e74c3c"
        ax_auto.scatter([x], [s], s=55, color=dot_c, zorder=5)
        ax_auto.text(x, s + 2.5, f"{s:.0f}", ha="center", va="bottom", fontsize=7, color=dot_c)

    ax_auto.text(
        n - 0.5, 15.0, lbl(labels, "autonomic_label_impaired", "Impaired"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_auto.text(
        n - 0.5, 40.0, lbl(labels, "autonomic_label_borderline", "Borderline"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_auto.text(
        n - 0.5, 60.0, lbl(labels, "autonomic_label_normal", "Normal"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_auto.text(
        n - 0.5, 77.5, lbl(labels, "autonomic_label_good", "Good"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_auto.text(
        n - 0.5, 92.5, lbl(labels, "autonomic_label_excellent", "Excellent"),
        ha="right", va="center", fontsize=8, color=_GRAY, alpha=0.8,
    )
    ax_auto.set_ylim(0.0, 100.0)
    ax_auto.set_ylabel(
        lbl(labels, "autonomic_score", "Autonomic Score") + " (0–100)", fontsize=10
    )
    ax_auto.grid(alpha=0.20, linestyle=":", axis="y")
    ax_auto.set_xticks(xs)
    ax_auto.set_xticklabels(session_labels, rotation=40, ha="right", fontsize=9)

    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()
    return fig
