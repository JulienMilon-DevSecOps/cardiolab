"""Readiness and protocol scoring functions.

**Resting HRV (baseline-relative) — :func:`readiness_score_multi` et al.**

Three complementary scoring approaches for resting HRV, all relative to
the personal baseline:

* :func:`readiness_score_multi` — classical multi-factor score combining
  time-domain metrics (RMSSD, HR) with the DFA α1 non-linear marker and a
  short-term trend component. Robust and well-suited for daily monitoring.
* :func:`readiness_score_nonlinear` — purely non-linear score built from the
  Poincaré and DFA metrics (SD1, SD1/SD2, DFA α1). Best used after at least
  7 sessions.
* :func:`readiness_score_composite` — weighted combination of the two above.

All resting scores are normalised to [0, 100]:

    * 50 = neutral (current session equals the personal baseline).
    * > 50 = above baseline → positive recovery signal.
    * < 50 = below baseline → possible fatigue or stress.

**Protocol-specific scores (absolute thresholds) — scientific references**

The following functions score other protocols against published clinical
thresholds. They do **not** require a personal baseline and return [0, 100]:

* :func:`hrr_score` — HRR1 (60 s recovery drop), Cole et al. 1999 (*NEJM*).
  Inflection at 18 bpm (mid-normal). ≥ 25 bpm → ~88 pts; < 12 bpm → ~13 pts.
* :func:`coherence_score_100` — maps ``coherence_score`` (%) to [0, 100] with
  amplified discrimination: ≥ 60 % → ≥ 75 pts (Lehrer & Gevirtz 2014).
* :func:`drift_score` — inverted score from ``drift_rate`` (bpm/min).
  No drift (0 bpm/min) → 100 pts; strong drift (≥ 3 bpm/min) → ~17 pts
  (Coyle & González-Alonso 2001).
* :func:`vo2max_score` — maps VO2max estimate (mL/kg/min) to [0, 100] via
  ACSM 2022 fitness categories. Inflection at 43 mL/kg/min (average adult).
"""

from __future__ import annotations

import math

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures

# ======================
# INTERNAL HELPERS
# ======================


def _dfa_score(dfa_alpha1: float) -> float:
    """Convert a DFA α1 value to a 0–100 score.

    Uses an absolute physiological threshold: α1 = 0.75 is the lower boundary
    of the normal resting range. Values below this threshold score < 50;
    values in the normal zone (0.75–1.25) score 50–95. A value of 0.0 is
    treated as "not computed" and returns the neutral 50.0.

    Args:
        dfa_alpha1: DFA short-term scaling exponent.

    Returns:
        Score in [0, 100].

    """
    if dfa_alpha1 <= 0.0 or math.isnan(dfa_alpha1):
        return 50.0

    return float(np.clip(50.0 + 50.0 * np.tanh((dfa_alpha1 - 0.75) * 3.0), 0.0, 100.0))


def _sd_ratio_score(sd_ratio: float) -> float:
    """Convert an SD1/SD2 ratio to a 0–100 score.

    Normal resting range is approximately 0.25–0.55. Below 0.25 indicates
    sympathetic dominance. A ratio of 0.0 is treated as "not computed".

    Args:
        sd_ratio: SD1/SD2 dimensionless ratio.

    Returns:
        Score in [0, 100].

    """
    if sd_ratio <= 0.0 or math.isnan(sd_ratio):
        return 50.0

    return float(np.clip(50.0 + 50.0 * np.tanh((sd_ratio - 0.25) * 5.0), 0.0, 100.0))


# ======================
# OURA-INSPIRED (legacy)
# ======================


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

    rmssd_score = 50.0 + 50.0 * np.tanh((current.rmssd / base_rmssd - 1.0) * 2.0)
    hr_score = 50.0 - 50.0 * np.tanh((current.mean_hr - base_hr) / 10.0)

    score = 0.7 * rmssd_score + 0.3 * hr_score

    return float(np.clip(score, 0.0, 100.0))


# ======================
# MULTI-FACTOR (classical + DFA α1)
# ======================


def readiness_score_multi(
    current: HRVFeatures,
    baseline: Baseline,
) -> float:
    """Compute a multi-factor readiness score combining linear and non-linear signals.

    Integrates four independent components:

    * **RMSSD** (35 %) — primary vagal activity, deviation from personal
      baseline median.
    * **Resting HR** (20 %) — elevated HR penalises the score.
    * **DFA α1** (25 %) — short-term fractal scaling exponent; normal resting
      range 0.75–1.25. Values below 0.75 strongly penalise the score.
      Treated as neutral (50) when not available or not yet computed.
    * **RMSSD trend** (20 %) — deviation from the rolling baseline median;
      detects day-to-day deterioration before it becomes visible in the
      absolute values.

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
    base_rmssd = baseline.median_rmssd()
    base_hr = baseline.mean_hr()

    if base_rmssd is None or base_hr is None:
        return 50.0

    # RMSSD (35 %) — deviation from personal baseline median
    rmssd_score = 50.0 + 50.0 * np.tanh((current.rmssd / base_rmssd - 1.0) * 2.0)

    # HR (20 %) — elevated HR penalises the score
    hr_score = 50.0 - 50.0 * np.tanh((current.mean_hr - base_hr) / 10.0)

    # DFA α1 (25 %) — absolute physiological threshold at 0.75
    dfa = _dfa_score(current.dfa_alpha1)

    # Trend (20 %) — current RMSSD vs rolling median
    rolling = baseline.rolling_rmssd_median()
    trend_score = (
        50.0 + 50.0 * np.tanh((current.rmssd - rolling[-1]) / 20.0) if rolling else 50.0
    )

    score = 0.35 * rmssd_score + 0.20 * hr_score + 0.25 * dfa + 0.20 * trend_score

    return float(np.clip(score, 0.0, 100.0))


# ======================
# NON-LINEAR
# ======================


def readiness_score_nonlinear(
    current: HRVFeatures,
    baseline: Baseline,
) -> float:
    """Compute a readiness score based exclusively on non-linear HRV features.

    Integrates three non-linear components that capture information
    orthogonal to time-domain metrics:

    * **DFA α1** (40 %) — short-term fractal scaling exponent. Normal resting
      range: 0.75–1.25. Below 0.75 strongly penalises the score. This
      component uses absolute physiological thresholds and does not require
      a personal baseline.
    * **SD1** (35 %) — Poincaré short-term variability (= RMSSD / √2),
      expressed as a deviation from the personal baseline median SD1. Captures
      the same parasympathetic signal as RMSSD but within a non-linear
      geometric framework.
    * **SD1/SD2** (25 %) — shape of the Poincaré ellipse. Normal resting
      range: 0.25–0.55. Values below 0.25 (flat ellipse) indicate sympathetic
      dominance and penalise the score. Uses absolute thresholds.

    A component returns the neutral value (50) when its input is not
    available (zero, ``nan``, or missing baseline).

    Returns 50.0 when the baseline is empty or when all non-linear metrics
    are unavailable.

    Args:
        current: HRV features of the session to score.
        baseline: Personal reference built from previous sessions. SD1
            baseline statistics are computed from ``baseline.median_sd1()``.

    Returns:
        Readiness score as a float in [0, 100].
        50 = neutral.
        > 50 = above baseline or above absolute reference thresholds.
        < 50 = below baseline or below reference thresholds.

    """
    # DFA α1 (40 %) — absolute threshold, no personal baseline required
    dfa = _dfa_score(current.dfa_alpha1)

    # SD1 (35 %) — deviation from personal baseline
    base_sd1 = baseline.median_sd1()

    if base_sd1 is not None and base_sd1 > 0.0 and current.sd1 > 0.0:
        sd1_score = float(
            np.clip(
                50.0 + 50.0 * np.tanh((current.sd1 / base_sd1 - 1.0) * 2.0),
                0.0,
                100.0,
            )
        )
    else:
        sd1_score = 50.0

    # SD1/SD2 (25 %) — absolute threshold (normal ≥ 0.25)
    sd_ratio = _sd_ratio_score(current.sd_ratio)

    score = 0.40 * dfa + 0.35 * sd1_score + 0.25 * sd_ratio

    return float(np.clip(score, 0.0, 100.0))


# ======================
# COMPOSITE
# ======================


def readiness_score_composite(
    current: HRVFeatures,
    baseline: Baseline,
    w_multi: float = 0.5,
    w_nonlinear: float = 0.5,
) -> float:
    """Compute a composite readiness score integrating classical and non-linear signals.

    Combines :func:`readiness_score_multi` (linear + DFA α1 + trend) with
    :func:`readiness_score_nonlinear` (DFA α1 + SD1 + SD1/SD2) into a single
    number that integrates the broadest picture of autonomic state.

    The two sub-scores are complementary:

    * ``readiness_score_multi`` is sensitive to **acute day-to-day changes**
      in RMSSD and HR and provides the RMSSD trend signal.
    * ``readiness_score_nonlinear`` adds the **structural complexity** of the
      heartbeat series (fractal correlations, Poincaré geometry) and is
      particularly useful for detecting overreaching before classical markers
      change.

    Custom weights allow you to emphasise one dimension over the other — e.g.
    increase ``w_nonlinear`` during high-load training blocks where DFA α1 is
    known to be the earliest fatigue marker.

    Args:
        current: HRV features of the session to score.
        baseline: Personal reference built from previous sessions.
        w_multi: Weight of :func:`readiness_score_multi` in the composite.
            Must be ≥ 0. Defaults to 0.5.
        w_nonlinear: Weight of :func:`readiness_score_nonlinear` in the
            composite. Must be ≥ 0. Defaults to 0.5.

    Returns:
        Composite readiness score as a float in [0, 100].

    Raises:
        ValueError: If ``w_multi + w_nonlinear == 0`` (undefined average).

    """
    total = w_multi + w_nonlinear

    if total == 0.0:
        raise ValueError("w_multi + w_nonlinear must be > 0")

    score_m = readiness_score_multi(current, baseline)
    score_nl = readiness_score_nonlinear(current, baseline)

    score = (w_multi * score_m + w_nonlinear * score_nl) / total

    return float(np.clip(score, 0.0, 100.0))


# ======================
# PROTOCOL-SPECIFIC ABSOLUTE SCORES
# ======================


def hrr_score(hrr_60: float) -> float:
    """Compute an HRR performance score from the 60-second heart rate drop.

    Maps HRR1 (bpm) to [0, 100] using a sigmoid centred at 18 bpm (mid-normal
    range), calibrated against the Cole et al. (1999) clinical thresholds:

    | HRR1 (bpm) | Category  | Approximate score |
    | ---------- | --------- | ----------------- |
    | ≥ 25       | Excellent | ≥ 88              |
    | 20 – 24    | Good      | 64 – 87           |
    | 12 – 19    | Normal    | 14 – 63           |
    | < 12       | Impaired  | < 14              |

    References:
        Cole, C. R., et al. (1999). Heart-rate recovery immediately after
        exercise as a predictor of mortality. *NEJM*, 341(18), 1351–1357.

    Args:
        hrr_60: Heart-rate drop from peak to 60 s post-exercise (bpm).

    Returns:
        Score in [0, 100].

    """
    return float(np.clip(50.0 + 50.0 * np.tanh((hrr_60 - 18.0) / 7.0), 0.0, 100.0))


def coherence_score_100(coherence_score: float) -> float:
    """Map a cardiac coherence percentage to a [0, 100] performance score.

    Amplifies discrimination around the clinical threshold (60 %) so that
    the good coherence zone (≥ 60 %) maps to ≥ 75 points and the poor zone
    (< 40 %) maps to ≤ 25 points, following Lehrer & Gevirtz (2014).

    | Coherence (%) | Clinical level | Approximate score |
    | ------------- | -------------- | ----------------- |
    | ≥ 60          | Good           | ≥ 75              |
    | 40 – 59       | Moderate       | 25 – 74           |
    | < 40          | Poor           | < 25              |

    References:
        Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability
        biofeedback: how and why does it work? *Frontiers in Psychology*, 5,
        756.

    Args:
        coherence_score: Raw coherence score [0, 100] from
            ``cardiac_coherence()``.

    Returns:
        Normalised performance score in [0, 100].

    """
    # Sigmoid centred at 50 % with steeper slope to spread good/poor apart
    return float(np.clip(50.0 + 50.0 * np.tanh((coherence_score - 50.0) / 20.0), 0.0, 100.0))


def drift_score(drift_rate: float) -> float:
    """Compute a performance score from the cardiac drift rate (bpm/min).

    Lower drift is better. The score is an inverted exponential decay so that
    no drift (0 bpm/min) gives the maximum score and strong drift (≥ 3 bpm/min)
    gives a very low score, matching the Coyle & González-Alonso (2001) limits.

    | Drift rate (bpm/min) | Category  | Approximate score |
    | -------------------- | --------- | ----------------- |
    | < 0.5                | No drift  | ≥ 82              |
    | 0.5 – 1.5            | Mild      | 55 – 81           |
    | 1.5 – 3.0            | Moderate  | 22 – 54           |
    | > 3.0                | Strong    | < 22              |

    References:
        Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift
        during prolonged exercise. *Exercise and Sport Sciences Reviews*,
        29(2), 88–92.

    Args:
        drift_rate: Slope of the HR–time linear regression (bpm/min).
            Negative values (HR decreasing) are treated as 0 (best case).

    Returns:
        Score in [0, 100].

    """
    rate = max(drift_rate, 0.0)  # negative drift treated as no-drift
    return float(np.clip(100.0 * (1.0 - np.tanh(rate / 2.5)), 0.0, 100.0))


def vo2max_score(vo2max: float) -> float:
    """Compute a fitness score from a VO2max estimate (mL/kg/min).

    Maps to [0, 100] using a sigmoid centred at 43 mL/kg/min (average
    adult, centre of the "Good" ACSM category), calibrated so that:

    | VO2max (mL/kg/min) | ACSM category | Approximate score |
    | ------------------ | ------------- | ----------------- |
    | ≥ 58               | Excellent     | ≥ 93              |
    | 48 – 57            | Very good     | 70 – 92           |
    | 38 – 47            | Good          | 30 – 69           |
    | 28 – 37            | Fair          | 8 – 29            |
    | < 28               | Poor          | < 8               |

    References:
        American College of Sports Medicine (2022). *ACSM's Guidelines for
        Exercise Testing and Prescription* (11th ed.). LWW.

    Args:
        vo2max: VO2max estimate in mL/kg/min. Must be > 0.

    Returns:
        Score in [0, 100]. Returns 0.0 if ``vo2max`` is not finite or ≤ 0.

    """
    if not math.isfinite(vo2max) or vo2max <= 0.0:
        return 0.0
    return float(np.clip(50.0 + 50.0 * np.tanh((vo2max - 43.0) / 12.0), 0.0, 100.0))
