"""Example 12 — Cardiac coherence, HRR, cardiac drift, and VO2max protocols.

All four protocols run on synthetic RR data — no database required.
Each block shows the protocol call, the key result fields, and the
corresponding scoring function from ``cardiolab.analytics.scoring``.

Protocols covered
-----------------
* ``cardiac_coherence``    — paced-breathing resonance score.
* ``heart_rate_recovery``  — autonomic rebound after peak effort.
* ``cardiac_drift``        — HR creep during sustained exercise.
* ``vo2max_from_hrv``      — aerobic capacity estimate from resting HRV.

Usage::

    python example/12_other_protocols.py

"""

from __future__ import annotations

import math
import warnings

import numpy as np

from cardiolab import (
    cardiac_coherence,
    cardiac_drift,
    coherence_score_100,
    drift_score,
    heart_rate_recovery,
    hrr_score,
    vo2max_from_hrv,
    vo2max_score,
)
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

rng = np.random.default_rng(42)


# ── 1. Cardiac coherence ──────────────────────────────────────────────────────
print("=" * 60)
print("1. Cardiac coherence — paced breathing at ~0.1 Hz (6 resp/min)")
print("=" * 60)

# Sinusoidal RR oscillating at 0.1 Hz — the hallmark of cardiac coherence.
# Mean HR ~60 bpm (RR ~1000 ms), amplitude ±100 ms.
n_beats = 320  # ~5 min
t = np.linspace(0, n_beats, n_beats)
rr_coherent = 1000 + 100 * np.sin(2 * np.pi * 0.1 * t) + rng.normal(0, 6, n_beats)
rr_coherent = rr_coherent.clip(600, 1400)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    result_coh = cardiac_coherence(RRSeries(rr_coherent))

print(f"  Coherence score   : {result_coh.coherence_score:.1f} %")
print(f"  Resonance freq.   : {result_coh.resonance_freq:.4f} Hz")
print(f"  Peak power        : {result_coh.peak_power:.2f} ms²")
print(f"  Mean HR           : {result_coh.mean_hr:.1f} bpm")
print(f"  Quality score     : {coherence_score_100(result_coh.coherence_score):.1f} / 100")
print()


# ── 2. Heart rate recovery ────────────────────────────────────────────────────
print("=" * 60)
print("2. Heart rate recovery — post-exercise autonomic rebound")
print("=" * 60)

# Start at peak effort (RR ~400 ms = 150 bpm), recover exponentially over ~3 min.
n_rec = 200
t_rec = np.arange(n_rec)
rr_hrr = 400 + 450 * (1 - np.exp(-t_rec / 35)) + rng.normal(0, 12, n_rec)
rr_hrr = rr_hrr.clip(300, 1600)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    result_hrr = heart_rate_recovery(RRSeries(rr_hrr))

print(f"  Peak HR           : {result_hrr.hr_peak:.1f} bpm")
print(f"  HR at 60 s        : {result_hrr.hr_at_60s:.1f} bpm")
print(f"  HRR1              : {result_hrr.hrr_60:.1f} bpm  ({result_hrr.hrr_60_category})")
if not math.isnan(result_hrr.hrr_120):
    print(f"  HRR2              : {result_hrr.hrr_120:.1f} bpm  ({result_hrr.hrr_120_category})")
print(f"  Quality score     : {hrr_score(result_hrr.hrr_60):.1f} / 100")
print()


# ── 3. Cardiac drift ──────────────────────────────────────────────────────────
print("=" * 60)
print("3. Cardiac drift — sustained effort at constant pace (~20 min)")
print("=" * 60)

# HR drifts from 140 → 155 bpm (dehydration / thermoregulation).
# RR: 429 ms → 387 ms over 1 400 beats (~23 min at 60 beats/min).
n_ex = 1400
rr_drift = np.linspace(429, 387, n_ex) + rng.normal(0, 8, n_ex)
rr_drift = rr_drift.clip(300, 900)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    result_drift = cardiac_drift(RRSeries(rr_drift))

print(f"  Drift rate        : {result_drift.drift_rate:.3f} bpm/min")
print(f"  Drift magnitude   : {result_drift.drift_magnitude:.1f} bpm  ({result_drift.interpretation})")
print(f"  R²                : {result_drift.r_squared:.3f}")
print(f"  Drift detected    : {result_drift.drift_detected}")
print(f"  Quality score     : {drift_score(result_drift.drift_rate):.1f} / 100")
print()


# ── 4. VO2max estimation ──────────────────────────────────────────────────────
print("=" * 60)
print("4. VO2max from resting HRV")
print("=" * 60)

# Resting HRV of a well-trained individual (high RMSSD ≈ good aerobic capacity).
rr_rest = rng.normal(980, 30, 320).clip(700, 1300)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    result_vo2 = vo2max_from_hrv(RRSeries(rr_rest), hr_max=185.0)

print(f"  VO2max (Esco-Flatt) : {result_vo2.vo2max_esco_flatt:.1f} mL/kg/min")
print(f"  VO2max (ln-RMSSD)   : {result_vo2.vo2max_ln_rmssd:.1f} mL/kg/min")
if not np.isnan(result_vo2.vo2max_uth):
    print(f"  VO2max (Uth)        : {result_vo2.vo2max_uth:.1f} mL/kg/min")
print(f"  Fitness category    : {result_vo2.fitness_category}")
print(f"  Resting HR          : {result_vo2.hr_rest:.1f} bpm")
print(f"  Quality score       : {vo2max_score(result_vo2.vo2max_esco_flatt):.1f} / 100")
print()
