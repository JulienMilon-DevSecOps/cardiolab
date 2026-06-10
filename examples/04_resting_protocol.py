"""Example 04 — Resting HRV protocol: from raw RR data to scored session.

Shows the complete resting workflow:
1. Build an ``RRSeries`` from raw RR intervals (ms).
2. Compute 14 HRV features via ``resting_hrv()``.
3. Score the session against a personal baseline.

The example works with synthetic data so no database or files are required.
For real recordings, use ``import_all(protocol="resting")`` to convert
raw Polar exports to JSON first (see the note at the bottom).

Usage::

    python example/04_resting_protocol.py

"""

from __future__ import annotations

import warnings

import numpy as np

from cardiolab import (
    Baseline,
    RRSeries,
    readiness_score_composite,
    readiness_score_multi,
)
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import PhysiologicalWarning

rng = np.random.default_rng(42)

# ── 1. Generate synthetic resting RR (5 min at ~60 bpm) ──────────────────────
print("=== Resting HRV protocol ===\n")

rr_intervals = rng.normal(1000, 40, 320).clip(600, 1400)

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    rr = RRSeries(rr_intervals)
    result = resting_hrv(rr, min_duration=0.0)

# ── 2. Inspect HRV features ───────────────────────────────────────────────────
print("HRV features")
print(f"  RMSSD      : {result.rmssd:.2f} ms   (normal range: 20–80 ms)")
print(f"  ln(RMSSD)  : {result.ln_rmssd:.3f}")
print(f"  SDNN       : {result.sdnn:.2f} ms")
print(f"  pNN50      : {result.pnn50:.1f} %")
print(f"  Mean HR    : {result.mean_hr:.1f} bpm")
print(f"  LF/HF      : {result.lf_hf:.2f}   (sympathovagal balance)")
print(f"  HF_nu      : {result.hf_nu:.2f}   (parasympathetic)")
print(f"  LF_nu      : {result.lf_nu:.2f}   (sympathetic)")
print(f"  Duration   : {result.duration:.0f} s")
print()

# ── 3. Score against a 30-session baseline ────────────────────────────────────
# Build a realistic 30-session history with slightly lower average RMSSD.
history_rmssd = rng.normal(55, 10, 30).clip(25, 100)
sessions = []
for _i, _rmssd_val in enumerate(history_rmssd):
    hist_rr = rng.normal(1050, 35, 300).clip(600, 1400)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PhysiologicalWarning)
        s = resting_hrv(RRSeries(hist_rr), min_duration=0.0)
    sessions.append(s)

baseline = Baseline.from_features(sessions)

score_multi = readiness_score_multi(result, baseline)
score_composite = readiness_score_composite(result, baseline)

print("Readiness scores")
print(f"  Multi-factor score  : {score_multi:.1f} / 100")
print(f"  Composite score     : {score_composite:.1f} / 100")
print(f"  Baseline RMSSD      : {baseline.mean_rmssd():.2f} ms")
print(f"  Baseline HR         : {baseline.mean_hr():.1f} bpm")
print()

# ── 4. Serialise to dict / JSON ───────────────────────────────────────────────
d = result.to_dict()
print("to_dict() keys:", list(d.keys()))

# ── Note — real-data pipeline ─────────────────────────────────────────────────
print("""
── For real Polar recordings ─────────────────────────────────────────────────
  1. Drop raw .txt / .csv files in cardiolab/datasets/raw/resting/
  2. python example/04_resting_protocol.py  →  imports to datasets/resting/
  3. python example/02_feed_database.py     →  persists to PostgreSQL
""")
