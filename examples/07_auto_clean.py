"""Example 07 — Artefact correction and the auto_clean parameter.

``RRSeries.correct_artifacts()`` classifies abnormal beats (Lipponen &
Tarvainen 2019) and **corrects** them instead of deleting them: an extra beat
is merged with the next interval, a missed beat is split in two, an ectopic or
long / short beat is replaced by an interpolated value. Deleting a beat
(``remove_outliers()``) joins its neighbours into a fake successive difference
and biases RMSSD, pNN50, SD1 and DFA α1.

``resting_hrv()`` and ``orthostatic_hrv()`` accept ``auto_clean=True``, which
runs ``correct_artifacts()`` then removes any remaining value outside
300–2000 ms (changed in v0.4.0 — earlier versions only deleted out-of-range
values).

When to use it:
- Raw exports (Polar, Garmin, optical sensors) that may contain motion
  artefacts or missed / extra beats.

When to clean manually:
- To read the ArtifactReport (share of corrected beats: above 5 %, the
  recording is unreliable) or to tune ``min_deviation`` / ``max_passes``.

Usage::

    python examples/07_auto_clean.py

"""

from __future__ import annotations

import warnings

import numpy as np

from cardiolab.features.time_domain import rmssd
from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries

rng = np.random.default_rng(42)

# ======================
# 1. Correct, don't delete
# ======================
print("=== 1. Ectopic, extra and missed beats: deletion vs correction ===")

t = np.arange(400)
truth = 900 + 35 * np.sin(2 * np.pi * t / 4.2) + rng.normal(0, 12, 400)
values = list(truth)
early = 0.65 * values[300]  # ectopic: premature beat + compensatory pause
values[301] += values[300] - early
values[300] = early
values[200:201] = [0.4 * values[200], 0.6 * values[200]]  # extra beat
values[100:102] = [values[100] + values[101]]  # missed beat
dirty = RRSeries(values)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    candidates = {
        "True signal": RRSeries(truth),
        "With artefacts": dirty,
        "remove_outliers() threshold": dirty.remove_outliers(),
        "remove_outliers() z-score": dirty.remove_outliers(method="zscore"),
        "correct_artifacts()": dirty.correct_artifacts()[0],
    }

for name, series in candidates.items():
    print(f"{name:<30} RMSSD {rmssd(series):5.1f} ms  ({len(series)} beats)")
# The threshold misses ectopic / extra beats (their values stay within
# 300–2000 ms); the z-score deletes beats (time axis shifted, which biases
# spectral analysis and DFA α1); the correction keeps every beat.

# ======================
# 2. Resting protocol — auto_clean
# ======================
print("\n=== 2. Resting protocol ===")

base_resting = rng.normal(857, 20, 400).clip(300, 1800)
base_resting[30] = 180.0  # artefact low
base_resting[200] = 2800.0  # artefact high

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    result_dirty = resting_hrv(RRSeries(base_resting), min_duration=0.0)
    result_clean = resting_hrv(
        RRSeries(base_resting), min_duration=0.0, auto_clean=True
    )

print(f"Without auto_clean — RMSSD: {result_dirty.rmssd:.2f} ms")
print(f"With    auto_clean — RMSSD: {result_clean.rmssd:.2f} ms")

# ======================
# 3. Orthostatic protocol — auto_clean
# ======================
print("\n=== 3. Orthostatic protocol ===")

supine_rr = rng.normal(920, 15, 350).clip(300, 1800)  # ~65 bpm
trans_rr = np.linspace(920, 705, 40)  # transition
standing_rr = rng.normal(705, 12, 350).clip(300, 1800)  # ~85 bpm
full = np.concatenate([supine_rr, trans_rr, standing_rr])
full[5] = 150.0  # artefact
full[600] = 2500.0  # artefact

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    result = orthostatic_hrv(RRSeries(full), min_phase_duration=60.0, auto_clean=True)

print(f"HR response    : +{result.hr_response:.1f} bpm")
print(f"Δ HF/FC        : {result.hf_hr_pct_change:.1f} %")
print(f"Interpretation : {result.interpretation}")
