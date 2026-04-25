from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import RestingResult


def detect_rmssd_anomaly(
    current: RestingResult,
    baseline: Baseline,
    method: str = "zscore",
) -> dict:
    """
    FR :
    Détecte une anomalie RMSSD.

    EN :
    Detects RMSSD anomaly.
    """

    if method == "simple":
        return _simple(current, baseline)
    elif method == "zscore":
        return _zscore(current, baseline)
    elif method == "rolling":
        return _rolling(current, baseline)
    else:
        raise ValueError(method)


def _simple(current, baseline):
    """
    FR : méthode simple basée sur % de variation
    EN : simple percentage-based method
    """

    base = baseline.mean_rmssd()
    if base is None:
        return {"status": "no_baseline"}

    delta = (current.rmssd - base) / base * 100

    return {"method": "simple", "delta_pct": delta, "status": _interpret(delta)}


def _zscore(current, baseline):
    """
    FR : méthode z-score
    EN : z-score method
    """

    values = [r.rmssd for r in baseline._get_recent()]
    if len(values) < 3:
        return {"status": "insufficient_data"}

    mean = np.mean(values)
    std = np.std(values)

    if std == 0:
        return {"status": "no_variability"}

    z = (current.rmssd - mean) / std

    return {
        "method": "zscore",
        "z": float(z),
        "status": "low" if z < -2 else "high" if z > 2 else "normal",
    }


def _rolling(current, baseline):
    """
    FR : méthode basée sur moyenne glissante
    EN : rolling baseline method
    """

    rolling = baseline.rolling_rmssd_median()
    if not rolling:
        return {"status": "insufficient_data"}

    base = rolling[-1]
    delta = (current.rmssd - base) / base * 100

    return {
        "method": "rolling",
        "baseline": base,
        "delta_pct": delta,
        "status": _interpret(delta),
    }


def _interpret(delta):
    """
    FR :
    Interprétation simple des variations.

    EN :
    Simple interpretation of variation.
    """
    
    if delta < -20:
        return "low_severe"
    elif delta < -10:
        return "low"
    elif delta > 20:
        return "high_severe"
    elif delta > 10:
        return "high"
    return "normal"