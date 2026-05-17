"""Example 06 — Physiological validation of RR intervals.

``RRSeries`` automatically emits a :class:`~cardiolab.signals.rr.PhysiologicalWarning`
when any interval falls outside the physiological range [300, 2000] ms
(HR < 30 bpm or HR > 200 bpm). These are almost always artefacts from optical
sensors, movement, or ectopic beats.

This example shows:
- How the warning is triggered.
- How to capture and inspect it.
- How to suppress it after cleaning with ``remove_outliers()``.
"""

from __future__ import annotations

import warnings

import numpy as np

from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

# ======================
# 1. Clean series — no warning
# ======================
print("=== 1. Clean series (no warning) ===")
clean_rr = RRSeries(np.random.default_rng(0).normal(857, 20, 300).clip(300, 1800))
print(f"n={len(clean_rr)}, mean_hr={clean_rr.mean_hr:.1f} bpm — no warning raised\n")

# ======================
# 2. Dirty series — triggers warning
# ======================
print("=== 2. Dirty series (outliers present) ===")
intervals = np.random.default_rng(1).normal(857, 20, 300).clip(300, 1800)
intervals[42] = 150.0  # artefact: HR > 200 bpm
intervals[200] = 2600.0  # artefact: HR < 23 bpm

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    dirty_rr = RRSeries(intervals)

for w in caught:
    print(f"[{w.category.__name__}] {w.message}")

# ======================
# 3. Clean after detection
# ======================
print("\n=== 3. After remove_outliers() ===")
clean = dirty_rr.remove_outliers()
print(f"Before: {len(dirty_rr)} intervals | After: {len(clean)} intervals")
print(f"Removed {len(dirty_rr) - len(clean)} outlier(s)")

# ======================
# 4. Silence the warning intentionally
# ======================
print("\n=== 4. Suppress PhysiologicalWarning intentionally ===")
with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    silent_rr = RRSeries(intervals)  # no output
print("Warning suppressed — proceed with care")
