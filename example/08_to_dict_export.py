"""Example 08 — Exporting HRV results with to_dict().

Every result dataclass in cardiolab exposes a ``to_dict()`` method that
returns a plain Python dict (no numpy types, no RR arrays). This makes it
trivial to:
- Serialise to JSON.
- Convert to a pandas DataFrame.
- Pass to an external API or database layer.

Covered in this example:
1. ``HRVFeatures.to_dict()``  — resting protocol output.
2. ``OrthostaticResult.to_dict()`` — nested orthostatic output.
3. JSON serialisation of both.
4. DataFrame construction from a list of sessions.
"""

from __future__ import annotations

import json
import math
import warnings

import numpy as np

from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries

rng = np.random.default_rng(0)


def _nan_to_none(obj):
    """Recursively replace NaN floats with None for JSON compatibility."""
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _nan_to_none(v) for k, v in obj.items()}
    return obj


# ======================
# 1. Resting — to_dict()
# ======================
print("=== 1. HRVFeatures.to_dict() ===")

rr = RRSeries(rng.normal(857, 20, 400).clip(300, 1800))
result = resting_hrv(rr, min_duration=0.0)
result.date = "2026-05-17"

d = result.to_dict()
print(json.dumps(d, indent=2))

# ======================
# 2. Orthostatic — to_dict()
# ======================
print("\n=== 2. OrthostaticResult.to_dict() ===")

supine = rng.normal(920, 15, 350).clip(300, 1800)
trans = np.linspace(920, 705, 40)
standing = rng.normal(705, 12, 350).clip(300, 1800)
ortho_rr = RRSeries(np.concatenate([supine, trans, standing]))

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    ortho_result = orthostatic_hrv(ortho_rr, min_phase_duration=60.0)

ortho_dict = _nan_to_none(ortho_result.to_dict())
print(f"interpretation : {ortho_dict['interpretation']}")
print(f"hr_response    : {ortho_dict['hr_response']:.1f} bpm")
print(f"supine rmssd   : {ortho_dict['phases']['supine']['features']['rmssd']:.2f} ms")
print(f"standing rmssd : {ortho_dict['phases']['standing']['features']['rmssd']:.2f} ms")

# ======================
# 3. DataFrame from multiple sessions
# ======================
print("\n=== 3. DataFrame from multiple resting sessions ===")
try:
    import pandas as pd

    sessions = []
    for i in range(5):
        rr_i = RRSeries(rng.normal(857 - i * 10, 20, 400).clip(300, 1800))
        f = resting_hrv(rr_i, min_duration=0.0)
        f.date = f"2026-05-{12 + i:02d}"
        sessions.append(f.to_dict())

    df = pd.DataFrame(sessions)
    print(df[["date", "rmssd", "mean_hr", "hf", "hf_hr"]].to_string(index=False))
except ImportError:
    print("pandas not installed — skipping DataFrame example")
