"""Example 11 — Spectral (frequency-domain) visualization.

Demonstrates all five functions from cardiolab.visualization.spectral_plots:

    plot_psd_welch        — PSD with VLF/LF/HF coloured bands
    plot_psd_comparison   — Welch vs AR overlay
    plot_lf_hf_evolution  — grouped bar chart of LF/HF balance across sessions
    plot_hrv_radar        — radar chart of 5 normalised HRV metrics
    plot_spectral_heatmap — sessions × frequency bands heatmap

Data source: JSON session files in cardiolab/datasets/resting/.
If none are found, three synthetic sessions are generated automatically.

Saved figures (example/figures/):
    11_01_psd_welch.png
    11_02_psd_ar.png
    11_03_psd_comparison.png
    11_04_lf_hf_evolution.png
    11_05_hrv_radar.png
    11_06_spectral_heatmap.png
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.spectral_plots import (
    plot_hrv_radar,
    plot_lf_hf_evolution,
    plot_psd_comparison,
    plot_psd_welch,
    plot_spectral_heatmap,
)

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "cardiolab" / "datasets" / "resting"
FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

DPI = 150

# ── Load or generate data ─────────────────────────────────────────────────────


def _load_sessions_from_files() -> list[tuple[str, RRSeries]]:
    """Return (label, RRSeries) pairs from JSON files in the dataset directory."""
    sessions = []
    for path in sorted(DATASET_DIR.glob("*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
            rr_values = data.get("rr_intervals", data.get("intervals", []))
            if rr_values:
                label = path.stem
                sessions.append((label, RRSeries(rr_values)))
        except Exception:  # noqa: BLE001, S110
            pass
    return sessions


def _synthetic_sessions(n: int = 3) -> list[tuple[str, RRSeries]]:
    """Generate n synthetic RR sessions with mild day-to-day variation."""
    sessions = []
    rng = np.random.default_rng(42)
    for i in range(n):
        mean_rr = 860 + i * 30  # gradual increase (recovery trend)
        std_rr = 40 - i * 5
        intervals = rng.normal(mean_rr, max(std_rr, 15), 300).clip(min=310)
        label = f"2026-05-{18 + i:02d}"
        sessions.append((label, RRSeries(intervals)))
    return sessions


def _compute_features(label: str, rr: RRSeries) -> HRVFeatures | None:
    """Compute HRVFeatures from an RRSeries, returning None on failure."""
    try:
        feats = resting_hrv(rr, min_duration=0.0)
        feats.date = label
        return feats
    except Exception:  # noqa: BLE001
        return None


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run all spectral visualization examples."""
    print("=== cardiolab — spectral visualization (example 11) ===\n")

    # Load data
    sessions = _load_sessions_from_files()
    source = "dataset files"
    if not sessions:
        sessions = _synthetic_sessions(3)
        source = "synthetic data"
    print(f"Sessions loaded from {source}: {len(sessions)}\n")

    # Use the first session for single-series charts
    primary_label, primary_rr = sessions[0]

    # Compute HRVFeatures for all sessions
    features_all: list[HRVFeatures] = []
    for lbl, rr in sessions:
        f = _compute_features(lbl, rr)
        if f is not None:
            features_all.append(f)
    if not features_all:
        print("Could not compute HRVFeatures — aborting.")
        return

    print("HRV features computed:\n")
    print(f"{'Session':<22} {'RMSSD':>7} {'LF_nu':>7} {'HF_nu':>7} {'LF/HF':>7}")
    print("-" * 54)
    for f in features_all:
        lf_hf = f.lf_hf if not math.isnan(f.lf_hf) else float("nan")
        print(
            f"{str(f.date):<22} {f.rmssd:>7.1f} {f.lf_nu:>7.3f} {f.hf_nu:>7.3f} "
            f"{lf_hf:>7.2f}"
        )
    print()

    # ── Figure 1 — Welch PSD ─────────────────────────────────────────────────
    print(f"Generating 11_01_psd_welch.png  [{primary_label}]")
    fig = plot_psd_welch(
        primary_rr,
        title=f"Power Spectral Density — {primary_label}",
        method="welch",
    )
    fig.savefig(FIGURES_DIR / "11_01_psd_welch.png", dpi=DPI, bbox_inches="tight")

    # ── Figure 2 — AR PSD ────────────────────────────────────────────────────
    print(f"Generating 11_02_psd_ar.png     [{primary_label}]")
    fig = plot_psd_welch(
        primary_rr,
        title=f"Power Spectral Density — {primary_label}",
        method="ar",
    )
    fig.savefig(FIGURES_DIR / "11_02_psd_ar.png", dpi=DPI, bbox_inches="tight")

    # ── Figure 3 — Welch vs AR overlay ──────────────────────────────────────
    print(f"Generating 11_03_psd_comparison.png  [{primary_label}]")
    fig = plot_psd_comparison(
        primary_rr,
        title=f"PSD Comparison — {primary_label}",
    )
    fig.savefig(FIGURES_DIR / "11_03_psd_comparison.png", dpi=DPI, bbox_inches="tight")

    # ── Figure 4 — LF/HF evolution ──────────────────────────────────────────
    print(f"Generating 11_04_lf_hf_evolution.png  [{len(features_all)} sessions]")
    fig = plot_lf_hf_evolution(
        features_all,
        title="LF/HF Autonomic Balance — Session Evolution",
    )
    fig.savefig(FIGURES_DIR / "11_04_lf_hf_evolution.png", dpi=DPI, bbox_inches="tight")

    # ── Figure 5 — HRV radar (last session) ─────────────────────────────────
    last_features = features_all[-1]
    print(f"Generating 11_05_hrv_radar.png  [{last_features.date}]")
    fig = plot_hrv_radar(
        last_features,
        title=f"HRV Radar Profile — {last_features.date}",
    )
    fig.savefig(FIGURES_DIR / "11_05_hrv_radar.png", dpi=DPI, bbox_inches="tight")

    # ── Figure 6 — Spectral heatmap ──────────────────────────────────────────
    print(f"Generating 11_06_spectral_heatmap.png  [{len(features_all)} sessions]")
    fig = plot_spectral_heatmap(
        features_all,
        title="Spectral Power Heatmap — Sessions × Bands",
    )
    fig.savefig(
        FIGURES_DIR / "11_06_spectral_heatmap.png", dpi=DPI, bbox_inches="tight"
    )

    print(f"\nAll figures saved to: {FIGURES_DIR.resolve()}\n")
    print("Figures generated:")
    for name in sorted(FIGURES_DIR.glob("11_*.png")):
        print(f"  {name.name}")


if __name__ == "__main__":
    main()
