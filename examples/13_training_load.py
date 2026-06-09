"""Example 13 — Training load: TRIMP, ATL, CTL, and TSB.

Demonstrates the complete training load pipeline:
1. Compute TRIMP using the HRV-based and Banister methods.
2. Build a 90-day synthetic session history.
3. Construct a ``TrainingLoad`` to get ATL / CTL / TSB curves.
4. Save the three standard training load plots to ``example/figures/``.

No database required — all data is generated synthetically.

Key concepts
------------
* **TRIMP** (Training Impulse) — daily training dose, proportional to
  duration and readiness (HRV-based) or cardiovascular intensity (Banister).
* **ATL** (Acute Training Load) — 7-day EMA of TRIMP; reflects current fatigue.
* **CTL** (Chronic Training Load) — 42-day EMA of TRIMP; reflects fitness base.
* **TSB** (Training Stress Balance) — CTL − ATL; a positive value means fresh,
  negative means fatigued.

Usage::

    python example/13_training_load.py

"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from datetime import date as _date
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np

from cardiolab.analytics.training_load import (
    TrainingLoad,
    trimp_banister,
    trimp_hrv_based,
)
from cardiolab.visualization.training_load_plots import (
    plot_atl_ctl_tsb,
    plot_trimp_history,
    plot_tsb_zones,
)

rng = np.random.default_rng(42)

FIGURES_DIR = Path(__file__).parent / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# ── 1. TRIMP methods ──────────────────────────────────────────────────────────
print("=" * 60)
print("1. TRIMP computation methods")
print("=" * 60)

# HRV-based TRIMP — scales duration by readiness score [0–100].
# High readiness → high training quality → high impulse.
t_hrv = trimp_hrv_based(duration_min=60, readiness_score=72.0)
print(f"\n  HRV-based TRIMP  (60 min, readiness=72) : {t_hrv:.2f}")

# Banister TRIMP — uses heart rate zone relative to athlete's HR range.
t_banister = trimp_banister(
    duration_min=60,
    hr_mean=145.0,
    hr_max=185.0,
    hr_rest=50.0,
    sex="male",
)
print(f"  Banister TRIMP   (60 min, HR 145/185/50) : {t_banister:.2f}")
print()


# ── 2. Build 90-day synthetic session history ─────────────────────────────────
print("=" * 60)
print("2. Build 90-day training history")
print("=" * 60)

today = _date(2026, 6, 9)
sessions = []

for i in range(90):
    d = today - timedelta(days=89 - i)
    # ~4–5 training days per week
    if rng.random() < 0.65:
        duration = float(rng.uniform(30, 100))
        readiness = float(rng.uniform(45, 88))
        sport = rng.choice(["running", "cycling", "strength", "trail"])
        trimp = trimp_hrv_based(duration, readiness)
        sessions.append({
            "date": str(d),
            "trimp": trimp,
            "sport_type": str(sport),
            "duration_min": duration,
        })

print(f"\n  Training days    : {len(sessions)} / 90")
print(f"  Average TRIMP    : {np.mean([s['trimp'] for s in sessions]):.1f}")
print()


# ── 3. Compute ATL / CTL / TSB ────────────────────────────────────────────────
print("=" * 60)
print("3. ATL / CTL / TSB — current training status")
print("=" * 60)

tl = TrainingLoad.from_sessions(sessions)

print(f"\n  Period           : {tl.dates[0]} → {tl.dates[-1]}  ({len(tl.dates)} days)")
print(f"  ATL (fatigue)    : {tl.atl[-1]:.1f}")
print(f"  CTL (fitness)    : {tl.ctl[-1]:.1f}")
print(f"  TSB (form)       : {tl.tsb[-1]:+.1f}  ({'fresh' if tl.tsb[-1] > 0 else 'fatigued'})")
print()

# TSB interpretation zones:
#   > +10  : Very fresh (low fitness risk of detraining)
#   0–+10  : Optimal race window
#   -10–0  : Normal training load
#   < -10  : Accumulated fatigue (monitor recovery)
if tl.tsb[-1] > 10:
    zone = "Very fresh — consider maintaining load"
elif tl.tsb[-1] > 0:
    zone = "Optimal form — good for competition"
elif tl.tsb[-1] > -10:
    zone = "Normal training phase"
else:
    zone = "High fatigue — prioritise recovery"
print(f"  Zone             : {zone}")
print()


# ── 4. Save plots ─────────────────────────────────────────────────────────────
print("=" * 60)
print("4. Training load plots → example/figures/")
print("=" * 60)

fig_atl = plot_atl_ctl_tsb(tl)
out_atl = FIGURES_DIR / "13_01_atl_ctl_tsb.png"
fig_atl.savefig(out_atl, dpi=150, bbox_inches="tight")
plt.close(fig_atl)
print(f"\n  Saved: {out_atl.name}")

fig_trimp = plot_trimp_history(tl, sessions=sessions)
out_trimp = FIGURES_DIR / "13_02_trimp_history.png"
fig_trimp.savefig(out_trimp, dpi=150, bbox_inches="tight")
plt.close(fig_trimp)
print(f"  Saved: {out_trimp.name}")

fig_zones = plot_tsb_zones(tl)
out_zones = FIGURES_DIR / "13_03_tsb_zones.png"
fig_zones.savefig(out_zones, dpi=150, bbox_inches="tight")
plt.close(fig_zones)
print(f"  Saved: {out_zones.name}")
print()
