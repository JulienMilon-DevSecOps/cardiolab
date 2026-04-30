"""Tools to analyze trends."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline


def trend_rmssd(baseline: Baseline) -> dict:
    """Analyze RMSSD trend.
    
    FR :
    Analyse la tendance du RMSSD.
    EN :
    Analyzes RMSSD trend.
    """
    values = [r.rmssd for r in baseline.history]

    if len(values) < 5:
        return {"status": "insufficient_data"}

    x = np.arange(len(values))
    y = np.array(values)

    slope = np.polyfit(x, y, 1)[0]

    return {
        "slope": float(slope),
        "trend": _interpret_trend(slope),
    }


def _interpret_trend(slope: float) -> str:
    """Interpret slope.
    
    FR :
    Interprète la pente.
    EN :
    Interprets slope.
    """
    if slope > 1:
        return "increasing"
    elif slope < -1:
        return "decreasing"
    return "stable"