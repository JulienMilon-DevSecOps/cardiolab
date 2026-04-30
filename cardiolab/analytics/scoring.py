"""DIfferents score from analyse RR Intervals."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures


def readiness_score_oura(current: HRVFeatures, baseline: Baseline) -> float:
    """Oura-like readiness score.
    
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



def readiness_score_multi(
    current: HRVFeatures,
    baseline: Baseline,
) -> float:
    """Compute a multi-factor readiness score based on.
    
    FR :
    Calcule un score de récupération multi-facteurs basé sur :
        - RMSSD (principal)
        - HR (charge physiologique)
        - HF (parasympathique)
        - tendance RMSSD (fatigue cumulée)
    Score entre 0 et 100.
    EN :
    Computes a multi-factor readiness score based on:
        - RMSSD (primary)
        - HR (physiological load)
        - HF (parasympathetic activity)
        - RMSSD trend (cumulative fatigue)
    Score between 0 and 100.
    """
    # ======================
    # BASELINE
    # ======================

    base_rmssd = baseline.median_rmssd()
    base_hr = baseline.mean_hr()

    if base_rmssd is None or base_hr is None:
        return 50.0

    # ======================
    # RMSSD SCORE (dominant)
    # ======================

    rmssd_ratio = current.rmssd / base_rmssd
    rmssd_score = 50 + 50 * np.tanh((rmssd_ratio - 1) * 2)

    # ======================
    # HR SCORE (inverse)
    # ======================

    hr_diff = current.mean_hr - base_hr
    hr_score = 50 - 50 * np.tanh(hr_diff / 10)

    # ======================
    # HF SCORE
    # ======================

    hf_ratio = current.hf / (current.lf + current.hf) if (current.lf + current.hf) > 0 else 0
    hf_score = 50 + 50 * (hf_ratio - 0.5)

    # ======================
    # TREND SCORE
    # ======================

    rolling = baseline.rolling_rmssd_median()

    if rolling:
        trend_diff = current.rmssd - rolling[-1]
        trend_score = 50 + 50 * np.tanh(trend_diff / 20)
    else:
        trend_score = 50.0

    # ======================
    # WEIGHTED SCORE
    # ======================

    score = (
        0.4 * rmssd_score +
        0.2 * hr_score +
        0.2 * hf_score +
        0.2 * trend_score
    )

    return float(np.clip(score, 0, 100))