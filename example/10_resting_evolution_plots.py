"""Example 10 — Resting HRV evolution plots over time.

Demonstrates how to visualise the progression of RMSSD and readiness score
across multiple resting sessions using ``cardiolab.visualization.resting_plots``:

* :func:`plot_resting_evolution`         — RMSSD and score over time.
* :func:`plot_resting_evolution_rolling` — same with a rolling-median RMSSD overlay.

Data source
-----------
Real sessions are loaded from ``cardiolab/datasets/resting/*.json`` when
available.  If fewer than two files are found, ten synthetic sessions spanning
10 days are generated (reproducible seed) so the script works out of the box.

Manual breakdown
----------------
The script also shows the underlying data manually (before calling the
ready-made plot functions) so you can see exactly what is computed and adapt
the approach to your own visualisations.

Usage
-----
Run from the project root::

    python example/10_resting_evolution_plots.py

Figures are saved to ``example/figures/`` at 150 dpi.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_oura
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.resting_plots import plot_resting_evolution_rolling

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

_DATA_GLOB = "cardiolab/datasets/resting/*.json"
_FIGURES_DIR = Path("example/figures")
_DPI = 150


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _save(fig: plt.Figure, name: str) -> None:
    path = _FIGURES_DIR / name
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {path}")


def _build_synthetic_sessions() -> list[dict]:
    """Return 10 synthetic session dicts (rr_intervals + date)."""
    rng = np.random.default_rng(42)
    sessions = []
    for i in range(10):
        # RMSSD trend: slight upward progression with noise
        mean_rr = 830 + i * 5 + rng.normal(0, 10)
        intervals = rng.normal(mean_rr, 30, 300).clip(min=310).tolist()
        sessions.append(
            {
                "date": f"2026-05-{10 + i:02d}",
                "rr_intervals": intervals,
            }
        )
    return sessions


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:
    """Load or generate sessions and produce the evolution plots."""
    print("=== cardiolab — resting HRV evolution ===\n")

    _FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. LOAD DATA
    # ------------------------------------------------------------------
    files = sorted(glob.glob(_DATA_GLOB))

    if len(files) >= 2:
        print(f"Loading {len(files)} session file(s) from {_DATA_GLOB}\n")
        sessions = []
        for path in files:
            with open(path) as f:
                sessions.append(json.load(f))
    else:
        print(
            "[info] Fewer than 2 session files found — using 10 synthetic sessions.\n"
        )
        sessions = _build_synthetic_sessions()

    # ------------------------------------------------------------------
    # 2. COMPUTE HRV FEATURES AND SCORES PROGRESSIVELY
    # ------------------------------------------------------------------
    dates: list[str] = []
    rmssd_values: list[float] = []
    rolling_medians: list[float | None] = []
    scores: list[float] = []
    past_features = []

    for session in sessions:
        rr = RRSeries(session["rr_intervals"])
        result = resting_hrv(rr)
        result.date = session["date"]

        baseline = (
            Baseline.from_features(past_features) if past_features else Baseline()
        )
        score = readiness_score_oura(result, baseline)

        rolling = baseline.rolling_rmssd_median()
        rolling_medians.append(float(rolling[-1]) if rolling else None)

        past_features.append(result)
        dates.append(session["date"])
        rmssd_values.append(result.rmssd)
        scores.append(score)

    # ------------------------------------------------------------------
    # 3. PRINT SUMMARY TABLE
    # ------------------------------------------------------------------
    print(f"{'Date':<14} {'RMSSD':>8} {'Rolling':>8} {'Score':>7}")
    print("─" * 44)
    for d, r, m, s in zip(dates, rmssd_values, rolling_medians, scores, strict=False):
        m_str = f"{m:8.1f}" if m is not None else "       —"
        print(f"{d:<14} {r:8.1f} {m_str} {s:7.1f}")
    print()

    # ------------------------------------------------------------------
    # 4. MANUAL PLOT — RMSSD + ROLLING MEDIAN
    # ------------------------------------------------------------------
    print("4. RMSSD evolution (manual plot)")
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(
        dates,
        rmssd_values,
        marker="o",
        color="#2980b9",
        linewidth=1.5,
        label="RMSSD (ms)",
    )
    valid_x = [d for d, m in zip(dates, rolling_medians, strict=False) if m is not None]
    valid_y = [m for m in rolling_medians if m is not None]
    if valid_y:
        ax.plot(
            valid_x,
            valid_y,
            linestyle="--",
            color="#e74c3c",
            linewidth=1.5,
            label="Rolling median (7 sessions)",
        )
    ax.set_title("RMSSD Evolution", fontsize=12, fontweight="bold")
    ax.set_ylabel("RMSSD (ms)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.25, linestyle=":")
    plt.tight_layout()
    _save(fig, "10_01_rmssd_evolution.png")

    # ------------------------------------------------------------------
    # 5. MANUAL PLOT — READINESS SCORE
    # ------------------------------------------------------------------
    print("5. Readiness score evolution (manual plot)")
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(dates, scores, marker="o", color="#27ae60", linewidth=1.5)
    ax.fill_between(dates, scores, alpha=0.12, color="#27ae60")
    ax.axhline(
        80,
        color="#2980b9",
        linewidth=0.8,
        linestyle=":",
        alpha=0.7,
        label="Good recovery (80)",
    )
    ax.axhline(
        60,
        color="#f39c12",
        linewidth=0.8,
        linestyle=":",
        alpha=0.7,
        label="Normal (60)",
    )
    ax.axhline(
        40,
        color="#e74c3c",
        linewidth=0.8,
        linestyle=":",
        alpha=0.7,
        label="Fatigue threshold (40)",
    )
    ax.set_title("Readiness Score Evolution", fontsize=12, fontweight="bold")
    ax.set_ylabel("Score (0 – 100)")
    ax.set_ylim(0, 105)
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25, linestyle=":")
    plt.tight_layout()
    _save(fig, "10_02_readiness_score.png")

    # ------------------------------------------------------------------
    # 6. READY-MADE FUNCTION (real files only)
    # ------------------------------------------------------------------
    if files:
        print("6. Ready-made plot_resting_evolution_rolling()")
        # This function opens its own figures and calls plt.show() by default;
        # we monkey-patch show() to save instead.
        _shown: list[plt.Figure] = []
        original_show = plt.show

        def _capture_show():
            for i, fig in enumerate(map(plt.figure, plt.get_fignums())):
                _save(fig, f"10_03_evolution_lib_{i + 1}.png")
            _shown.extend(plt.get_fignums())

        plt.show = _capture_show  # type: ignore[assignment]
        try:
            plot_resting_evolution_rolling(_DATA_GLOB)
        finally:
            plt.show = original_show  # type: ignore[assignment]
    else:
        print(
            "6. plot_resting_evolution_rolling() — skipped (needs real session files)"
        )

    print(f"\nAll figures saved to {_FIGURES_DIR}/")


if __name__ == "__main__":
    main()
