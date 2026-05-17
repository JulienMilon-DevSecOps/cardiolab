"""Example 07 — auto_clean parameter in HRV protocols.

Both ``resting_hrv()`` and ``orthostatic_hrv()`` accept an ``auto_clean=True``
flag that applies ``RRSeries.remove_outliers()`` (threshold method, [300, 2000] ms)
before any computation. This is equivalent to calling ``remove_outliers()``
manually, but more convenient for quick pipelines.

When to use ``auto_clean``:
- Raw exports from optical sensors (wrist PPG) that are not pre-filtered.
- Files imported from Polar or Garmin that may contain motion artefacts.

When NOT to use ``auto_clean``:
- If you need fine-grained control over the cleaning parameters (e.g. custom
  bounds or z-score method), clean manually before calling the protocol.
"""

from __future__ import annotations

import warnings

import numpy as np

from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries

rng = np.random.default_rng(42)

# ======================
# 1. Resting protocol
# ======================
print("=== 1. Resting protocol ===")

base_resting = rng.normal(857, 20, 400).clip(300, 1800)
base_resting[30] = 180.0  # artefact low
base_resting[200] = 2800.0  # artefact high

dirty = RRSeries(base_resting)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    result_dirty = resting_hrv(dirty, min_duration=0.0, auto_clean=False)
    result_clean = resting_hrv(dirty, min_duration=0.0, auto_clean=True)

print(f"Without auto_clean — RMSSD: {result_dirty.rmssd:.2f} ms")
print(f"With    auto_clean — RMSSD: {result_clean.rmssd:.2f} ms")

# ======================
# 2. Orthostatic protocol
# ======================
print("\n=== 2. Orthostatic protocol ===")

supine_rr = rng.normal(920, 15, 350).clip(300, 1800)  # ~65 bpm
trans_rr = np.linspace(920, 705, 40)  # transition
standing_rr = rng.normal(705, 12, 350).clip(300, 1800)  # ~85 bpm
full = np.concatenate([supine_rr, trans_rr, standing_rr])
full[5] = 150.0  # artefact
full[600] = 2500.0  # artefact

dirty_ortho = RRSeries(full)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    result = orthostatic_hrv(dirty_ortho, min_phase_duration=60.0, auto_clean=True)

print(f"HR response    : +{result.hr_response:.1f} bpm")
print(f"Δ HF/FC        : {result.hf_hr_pct_change:.1f} %")
print(f"Interpretation : {result.interpretation}")
