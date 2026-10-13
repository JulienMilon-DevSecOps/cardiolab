"""Example 09 — Raw RR signal visualisation.

Demonstrates the five plot functions in ``cardiolab.visualization.rr_plots``:

* :func:`plot_rr_tachogram`  — time series of RR intervals with HR secondary axis.
* :func:`plot_rr_distribution` — histogram + KDE of the interval distribution.
* :func:`plot_rr_filtered`  — raw signal overlaid with filtered version, artefacts in red.
* :func:`plot_rr_comparison` — stacked tachograms for multi-session comparison.
* :func:`plot_rr_summary`   — 2×2 compound figure combining all views.

Data source
-----------
Your own raw RR files (``.txt`` / ``.csv`` / ``.rr``) in
``cardiolab/datasets/raw/resting/`` when available; otherwise the first three
resting recordings shipped with cardiolab (``cardiolab.datasets``), so the
script works out of the box on real data.

Usage
-----
Run from the project root::

    python examples/09_rr_signal_plots.py

Figures are saved to ``examples/figures/`` at 150 dpi.
No display window is opened — safe for headless / CI environments.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from cardiolab.datasets import list_samples, load_sample
from cardiolab.sensors_tools import parse_rr_file
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.rr_plots import (
    plot_rr_comparison,
    plot_rr_distribution,
    plot_rr_filtered,
    plot_rr_summary,
    plot_rr_tachogram,
)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

_DATA_DIR = Path("cardiolab/datasets/raw/resting")
_RR_SUFFIXES = {".txt", ".csv", ".rr"}
_FIGURES_DIR = Path("examples/figures")
_DPI = 150


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _load_sessions() -> tuple[list[RRSeries], list[str]]:
    """Return (rr_list, labels) from your raw RR files or the shipped samples."""
    files = sorted(p for p in _DATA_DIR.glob("*") if p.suffix in _RR_SUFFIXES)

    if files:
        rr_list, labels = [], []
        for path in files:
            rr_list.append(RRSeries(parse_rr_file(path)["rr_intervals"]))
            labels.append(path.stem)
        return rr_list, labels

    print(f"[info] No file in {_DATA_DIR} — using the cardiolab sample recordings.")
    rr_list = [load_sample("resting", i) for i in range(3)]
    labels = [s["date"] for s in list_samples("resting")[:3]]
    return rr_list, labels


def _save(fig: plt.Figure, name: str) -> None:
    path = _FIGURES_DIR / name
    fig.savefig(path, dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved → {path}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all five visualisation examples and save the figures."""
    print("=== cardiolab — RR signal visualisation ===\n")

    _FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    rr_list, labels = _load_sessions()
    rr = rr_list[0]
    label = labels[0]

    print(
        f"Loaded {len(rr_list)} session(s). Using '{label}' for single-session plots."
    )
    print(f"  n={len(rr)}, duration={rr.duration:.0f}s, mean HR={rr.mean_hr:.1f} bpm\n")

    # ------------------------------------------------------------------
    # 1. TACHOGRAM
    # ------------------------------------------------------------------
    print("1. Tachogram")
    fig = plot_rr_tachogram(
        rr,
        title=f"RR Tachogram — {label}",
        show_mean=True,
        show_band=True,
        show_hr_axis=True,
    )
    _save(fig, "09_01_tachogram.png")

    # ------------------------------------------------------------------
    # 2. DISTRIBUTION
    # ------------------------------------------------------------------
    print("2. Distribution")
    fig = plot_rr_distribution(
        rr,
        title=f"RR Distribution — {label}",
        show_kde=True,
        show_stats=True,
    )
    _save(fig, "09_02_distribution.png")

    # ------------------------------------------------------------------
    # 3. RAW VS FILTERED
    # ------------------------------------------------------------------
    print("3. Raw vs filtered")
    rr_clean = rr.remove_outliers(method="zscore")
    fig = plot_rr_filtered(
        rr,
        rr_filtered=rr_clean,
        title=f"Raw vs Filtered — {label}",
    )
    _save(fig, "09_03_filtered.png")

    # ------------------------------------------------------------------
    # 4. MULTI-SESSION COMPARISON
    # ------------------------------------------------------------------
    print("4. Multi-session comparison")
    n_compare = min(len(rr_list), 3)
    if n_compare == 1:
        print("   (only one session available — single-panel comparison)")
    fig = plot_rr_comparison(
        rr_list[:n_compare],
        labels=labels[:n_compare],
        title="Multi-session RR Comparison",
        normalize_time=False,
    )
    _save(fig, "09_04_comparison.png")

    # ------------------------------------------------------------------
    # 5. 2×2 SUMMARY
    # ------------------------------------------------------------------
    print("5. 2×2 Summary")
    fig = plot_rr_summary(
        rr,
        title=f"Full RR Analysis — {label}",
    )
    _save(fig, "09_05_summary.png")

    print(f"\nAll figures saved to {_FIGURES_DIR}/")


if __name__ == "__main__":
    main()
