"""Example 05 — Orthostatic HRV protocol: supine → standing autonomic response.

Shows the complete orthostatic workflow:
1. Build a continuous ``RRSeries`` covering a supine phase, a brief
   transition, and a standing phase.
2. Run ``orthostatic_hrv()`` which auto-detects the postural change.
3. Inspect the phase segments and the cardiac autonomic response.
4. Score the result with ``orthostatic_score()``.

Works entirely with synthetic data — no database or files required.
For real recordings, use ``import_all(protocol="orthostatic")`` to convert
raw Polar exports first (see the note at the bottom).

Usage::

    python example/05_orthostatic_protocol.py

"""

from __future__ import annotations

import warnings

import numpy as np

from cardiolab import OrthostaticResult, orthostatic_hrv, orthostatic_score
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

rng = np.random.default_rng(42)

# ── 1. Build synthetic orthostatic RR series ──────────────────────────────────
print("=== Orthostatic HRV protocol ===\n")

# Supine phase: ~5 min at 60 bpm (HR low → long RR)
supine = rng.normal(980, 18, 320).clip(700, 1300)

# Transition: ~15 s of sympathetic activation (HR rises quickly)
transition = np.linspace(980, 720, 20) + rng.normal(0, 15, 20)

# Standing phase: ~5 min at 83 bpm (HR high → short RR)
standing = rng.normal(725, 15, 350).clip(500, 1100)

rr_full = np.concatenate([supine, transition, standing])

with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    rr = RRSeries(rr_full)
    result: OrthostaticResult = orthostatic_hrv(rr, min_phase_duration=0.0)

# ── 2. Inspect phase segments ─────────────────────────────────────────────────
print("Phase segments")
if result.phases.supine:
    s = result.phases.supine
    print(
        f"  Supine   — dur={s.duration_sec:.0f}s  HR={s.features.mean_hr:.1f} bpm  RMSSD={s.features.rmssd:.1f} ms"
    )
if result.phases.standing:
    st = result.phases.standing
    print(
        f"  Standing — dur={st.duration_sec:.0f}s  HR={st.features.mean_hr:.1f} bpm  RMSSD={st.features.rmssd:.1f} ms"
    )
print()

# ── 3. Inspect the autonomic response ────────────────────────────────────────
print("Autonomic response")
print(f"  HR response           : {result.hr_response:+.1f} bpm  (standing − supine)")
print(f"  HF response           : {result.hf_response_pct:+.1f} %  (HF power change)")
print(f"  Interpretation        : {result.interpretation}")
print()

# ── 4. Score the result ───────────────────────────────────────────────────────
score = orthostatic_score(result.hr_response, result.hf_response_pct)
print(f"Orthostatic score : {score:.1f} / 100")
print()

# ── 5. Serialise to dict ──────────────────────────────────────────────────────
d = result.to_dict()
print("to_dict() keys:", list(d.keys()))

# ── Note — real-data pipeline ─────────────────────────────────────────────────
print("""
── For real Polar recordings ─────────────────────────────────────────────────
  Requirements: ≥ 5 min supine + transition + ≥ 5 min standing (≥ 12 min total)

  1. Drop raw .txt / .csv files in cardiolab/datasets/raw/orthostatic/
  2. python example/05_orthostatic_protocol.py  →  imports to datasets/orthostatic/
  3. Load and analyse with orthostatic_hrv():

       import json
       from cardiolab.signals.rr import RRSeries
       from cardiolab.protocols.orthostatic import orthostatic_hrv

       with open("cardiolab/datasets/orthostatic/2026-05-15 08-00-00.json") as f:
           data = json.load(f)
       rr = RRSeries(data["rr_intervals"])
       result = orthostatic_hrv(rr)
""")
