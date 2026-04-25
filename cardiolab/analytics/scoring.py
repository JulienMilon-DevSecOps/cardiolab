from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import RestingResult


def readiness_score_oura(current: RestingResult, baseline: Baseline) -> float:
    """
    FR :
    Score de récupération inspiré Oura.

    EN :
    Oura-like readiness score.
    """

    base_rmssd = baseline.median_rmssd()
    base_hr = baseline.mean_hr()

    if base_rmssd is None or base_hr is None:
        return 50.0

    # RMSSD contribution
    ratio = current.rmssd / base_rmssd
    rmssd_score = 50 + 50 * np.tanh((ratio - 1) * 2)

    # HR penalty
    hr_diff = current.mean_hr - base_hr
    hr_score = 50 - 50 * np.tanh(hr_diff / 10)

    score = 0.7 * rmssd_score + 0.3 * hr_score

    return float(np.clip(score, 0, 100))