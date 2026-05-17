"""Readiness scoring functions based on HRV features and personal baseline."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures


def readiness_score_oura(current: HRVFeatures, baseline: Baseline) -> float:
    """Compute a readiness score inspired by the Oura ring methodology.

    Combines a RMSSD component (dominant, 70 % weight) and a resting heart
    rate component (30 % weight). Both contributions are computed as deviations
    from the personal baseline median using a tanh transfer function that
    smoothly saturates at the extremes.

    Returns 50.0 (neutral) when the baseline is empty or uninitialised.

    Args:
        current: HRV features of the session to score.
        baseline: Personal reference built from previous sessions. Requires
            at least one recorded session to produce a meaningful score.

    Returns:
        Readiness score as a float in [0, 100].
        50 = neutral (current equals baseline).
        > 50 = better than baseline.
        < 50 = worse than baseline.

    """
    base_rmssd = baseline.median_rmssd()
    base_hr = baseline.mean_hr()

    if base_rmssd is None or base_hr is None:
        return 50.0

    # RMSSD contribution
    ratio = current.rmssd / base_rmssd
    rmssd_score = 50 + 50 * np.tanh((ratio - 1) * 2)

    # HR penalty: elevated resting HR reduces the score
    hr_diff = current.mean_hr - base_hr
    hr_score = 50 - 50 * np.tanh(hr_diff / 10)

    score = 0.7 * rmssd_score + 0.3 * hr_score

    return float(np.clip(score, 0, 100))


def readiness_score_multi(
    current: HRVFeatures,
    baseline: Baseline,
) -> float:
    """Compute a multi-factor readiness score from four independent components.

    Extends ``readiness_score_oura`` by adding HF band power and a RMSSD
    trend component. Each component is weighted to reflect its physiological
    relevance:

    * RMSSD ratio vs. baseline median  — 40 %
    * Resting HR deviation             — 20 %
    * HF relative power (HF_nu)        — 20 %
    * RMSSD vs. rolling median trend   — 20 %

    Returns 50.0 (neutral) when the baseline is empty or uninitialised.

    Args:
        current: HRV features of the session to score.
        baseline: Personal reference built from previous sessions. A rolling
            window of at least ``baseline.window`` sessions is needed to
            activate the trend component; otherwise that component defaults
            to 50.

    Returns:
        Readiness score as a float in [0, 100].
        50 = neutral (current equals baseline on all components).
        > 50 = better than baseline.
        < 50 = worse than baseline.

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

    hf_ratio = (
        current.hf / (current.lf + current.hf) if (current.lf + current.hf) > 0 else 0
    )
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

    score = 0.4 * rmssd_score + 0.2 * hr_score + 0.2 * hf_score + 0.2 * trend_score

    return float(np.clip(score, 0, 100))
