"""Readiness and protocol scoring functions.

**Resting HRV (baseline-relative) — :func:`readiness_score_multi` et al.**

Three complementary scoring approaches for resting HRV, all relative to
the personal baseline:

* :func:`readiness_score_multi` — classical multi-factor score combining
  time-domain metrics (RMSSD, HR) with the DFA α1 non-linear marker and a
  7-day lnRMSSD trend component (Plews). Robust and well-suited for daily
  monitoring.
* :func:`readiness_score_nonlinear` — non-linear score (DFA α1, SD1/SD2),
  each against the athlete's history. Needs 6 previous measurement days.
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
* :func:`coherence_score_100` — maps ``coherence_score`` (%, McCraty &
  Shaffer 2015) to [0, 100]: ≥ 50 % (good) → ≥ 84 pts, < 30 % → < 16 pts.
* :func:`drift_score` — inverted score from ``drift_rate`` (bpm/min).
  No drift (0 bpm/min) → 100 pts; strong drift (≥ 3 bpm/min) → ~17 pts
  (Coyle & González-Alonso 2001).
* :func:`vo2max_score` — percentile of the VO2max estimate among people of
  the same sex and age (FRIEND registry, Kaminsky et al. 2015); without age
  and sex, a sigmoid centred at 43 mL/kg/min (average adult).
* :func:`orthostatic_score` — composite autonomic score for the postural
  (tilt) test: 80 % ΔHR component (Brignole et al. 2018 ESC Guidelines;
  Sheldon et al. 2015 POTS consensus) + 20 % HF vagal-withdrawal component
  (Task Force ESC/NASPE 1996). Normal ΔHR range: 10–25 bpm.
"""

from __future__ import annotations

import math

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.monitoring import (
    dfa_alpha1_score,
    ln_rmssd_day_score,
    ln_rmssd_trend_score,
    resting_hr_score,
    sd_ratio_score,
)
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import vo2max_percentile

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
    """Compute the readiness score from four components, each against the athlete's own history.

    * **lnRMSSD of the day** (45 %) — today's lnRMSSD against the daily
      values of the previous 28 days, in units of the athlete's variability
      (:func:`~cardiolab.analytics.monitoring.ln_rmssd_day_score`; Kiviniemi
      et al. 2007, Plews et al. 2013).
    * **Resting HR** (25 %) — today's HR against the previous 28 days, in
      units of the athlete's variability, lower is better
      (:func:`~cardiolab.analytics.monitoring.resting_hr_score`). HR and HRV
      carry complementary information (Buchheit 2014).
    * **lnRMSSD trend** (20 %) — change of the 7-day rolling mean of lnRMSSD
      versus the previous week, in SWC units
      (:func:`~cardiolab.analytics.monitoring.ln_rmssd_trend_score`).
    * **DFA α1** (10 %) — today's α1 against the previous 28 days, lower is
      better (:func:`~cardiolab.analytics.monitoring.dfa_alpha1_score`).

    Components without enough history are neutral (50): lnRMSSD, HR and
    DFA α1 need 6 previous measurement days, the trend ≈ 14 days. Their weight is not
    redistributed. Returns 50.0 when the baseline is empty.

    The weights are cardiolab's heuristic — no study validates a precise
    weighting of these markers.

    Changed in 0.5.0: weights were RMSSD 35 / HR 20 / DFA α1 25 / trend 20;
    RMSSD was scored as a ratio to the median of 7 sessions, HR on a fixed
    10 bpm scale against the mean of 7 sessions, DFA α1 against the fixed
    0.75 threshold (higher is better), and the trend compared today's RMSSD
    with the same median.

    Args:
        current: HRV features of the session to score (dated, for the
            history-based components).
        baseline: Personal reference built from previous sessions
            (``poor`` sessions excluded).

    Returns:
        Readiness score as a float in [0, 100].
        50 = neutral (current equals baseline on all components).
        > 50 = better than baseline.
        < 50 = worse than baseline.

    """
    if baseline.mean_hr() is None:
        return 50.0

    # lnRMSSD of the day (45 %) — vs the athlete's previous 28 days
    rmssd_score = ln_rmssd_day_score(current, baseline)

    # HR (25 %) — vs the athlete's previous 28 days, lower is better
    hr_score = resting_hr_score(current, baseline)

    # Trend (20 %) — 7-day lnRMSSD mean vs previous week, in SWC units
    trend_score = ln_rmssd_trend_score(current, baseline)

    # DFA α1 (10 %) — vs the athlete's previous 28 days, lower is better
    dfa = dfa_alpha1_score(current, baseline)

    score = 0.45 * rmssd_score + 0.25 * hr_score + 0.20 * trend_score + 0.10 * dfa

    return float(np.clip(score, 0.0, 100.0))


# ======================
# NON-LINEAR
# ======================


def readiness_score_nonlinear(
    current: HRVFeatures,
    baseline: Baseline,
) -> float:
    """Compute a readiness score from non-linear HRV features only.

    Two components, each against the athlete's previous 28 days:

    * **DFA α1** (50 %) — short-term scaling exponent, **lower is better**
      (vagal activity lowers α1, sympathetic activity raises it —
      Castiglioni et al. 2011); see
      :func:`~cardiolab.analytics.monitoring.dfa_alpha1_score`.
    * **SD1/SD2** (50 %) — shape of the Poincaré ellipse, **higher is
      better** (a marker of autonomic balance, correlated with LF/HF —
      Shaffer & Ginsberg 2017); see
      :func:`~cardiolab.analytics.monitoring.sd_ratio_score`.

    Each component is neutral (50) with fewer than 6 previous values or when
    its metric was not computed. Evidence for these markers at rest is weaker
    than for lnRMSSD: this score complements :func:`readiness_score_multi`,
    it is not the stored score de forme.

    Changed in 0.5.0: DFA α1 40 % (fixed 0.75 threshold, higher is better),
    SD1 35 % (ratio to the median of 7 sessions — the RMSSD signal again, as
    SD1 = RMSSD / √2) and SD1/SD2 25 % (absolute scale centred at 0.25).

    Args:
        current: HRV features of the session to score (dated).
        baseline: Personal reference built from previous sessions.

    Returns:
        Readiness score as a float in [0, 100]; 50 = neutral.

    """
    dfa = dfa_alpha1_score(current, baseline)
    ratio = sd_ratio_score(current, baseline)
    return float(np.clip(0.5 * dfa + 0.5 * ratio, 0.0, 100.0))


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

    Combines :func:`readiness_score_multi` (lnRMSSD, HR, trend, DFA α1) with
    :func:`readiness_score_nonlinear` (DFA α1, SD1/SD2) into a single
    number that integrates the broadest picture of autonomic state.

    The two sub-scores are complementary:

    * ``readiness_score_multi`` is sensitive to **acute day-to-day changes**
      in RMSSD and HR and provides the RMSSD trend signal.
    * ``readiness_score_nonlinear`` adds the **structure** of the heartbeat
      series (fractal correlations, Poincaré geometry). Its evidence as a
      recovery marker at rest is weaker than for lnRMSSD, and SD1 repeats the
      RMSSD signal (SD1 = RMSSD / √2).

    Custom weights allow you to emphasise one dimension over the other. The
    stored score de forme is :func:`readiness_score_multi`, not this one.

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

    ``coherence_score`` is the share of the whole spectrum in the resonance
    peak (McCraty & Shaffer 2015; see
    :func:`~cardiolab.protocols.cardiac_coherence.cardiac_coherence`).
    Sigmoid centred at 40 %:

    | Coherence (%) | Coherence ratio | Level    | Approximate score |
    | ------------- | --------------- | -------- | ----------------- |
    | ≥ 50          | ≥ 1             | Good     | ≥ 84              |
    | 30 – 50       | 0.43 – 1        | Moderate | 16 – 84           |
    | < 30          | < 0.43          | Low      | < 16              |

    The levels are cardiolab thresholds — no validated cut-off exists for the
    coherence ratio: 50 % is the point where the peak holds as much power as
    the rest of the spectrum (CR = 1); spontaneous breathing at rest scores
    ≈ 5–30 % (measured on real resting recordings).

    Changed in 0.5.0: centred at 50 % with good ≥ 60 % — calibrated for the
    former score (resonance band only), under which rest already scored
    50–60 %.

    References:
        McCraty, R., & Shaffer, F. (2015). Heart rate variability: new
        perspectives on physiological mechanisms, assessment of
        self-regulatory capacity, and health risk. *Global Advances in Health
        and Medicine*, 4(1), 46–61.

    Args:
        coherence_score: Coherence score in % from ``cardiac_coherence()``.

    Returns:
        Normalised performance score in [0, 100].

    """
    return float(
        np.clip(50.0 + 50.0 * np.tanh((coherence_score - 40.0) / 12.0), 0.0, 100.0)
    )


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


def vo2max_score(
    vo2max: float, age: float | None = None, sex: str | None = None
) -> float:
    """Compute a fitness score from a VO2max estimate (mL/kg/min).

    **With age and sex** (added in 0.5.0): the score is the athlete's
    percentile among people of the same sex and age decade — FRIEND registry
    norms (Kaminsky et al. 2015), see
    :func:`~cardiolab.protocols.vo2max.vo2max_percentile`. 50 = median of
    the athlete's sex and age; 90 = better than 90 % of them.

    **Without them**: a sigmoid centred at 43 mL/kg/min on the fixed adult
    scale:

    | VO2max (mL/kg/min) | Category      | Approximate score |
    | ------------------ | ------------- | ----------------- |
    | ≥ 58               | Excellent     | ≥ 92              |
    | 48 – 57            | Very good     | 70 – 92           |
    | 38 – 47            | Good          | 30 – 69           |
    | 28 – 37            | Fair          | 8 – 29            |
    | < 28               | Poor          | < 8               |

    References:
        Kaminsky, L. A., Arena, R., & Myers, J. (2015). Reference standards
        for cardiorespiratory fitness measured with cardiopulmonary exercise
        testing. *Mayo Clinic Proceedings*, 90(11), 1515–1523.

    Args:
        vo2max: VO2max estimate in mL/kg/min. Must be > 0.
        age: Age in years.
        sex: ``"male"`` or ``"female"``.

    Returns:
        Score in [0, 100]. Returns 0.0 if ``vo2max`` is not finite or ≤ 0.

    """
    if not math.isfinite(vo2max) or vo2max <= 0.0:
        return 0.0
    percentile = vo2max_percentile(vo2max, age, sex)
    if percentile is not None:
        return float(np.clip(percentile, 0.0, 100.0))
    return float(np.clip(50.0 + 50.0 * np.tanh((vo2max - 43.0) / 12.0), 0.0, 100.0))


def orthostatic_readiness_score(supine: HRVFeatures, baseline: Baseline) -> float:
    """Compute a readiness score from the supine phase of an orthostatic test.

    The supine phase of an orthostatic test is physiologically equivalent to a
    standard resting HRV session.  Applying :func:`readiness_score_multi` to
    the supine features therefore gives a baseline-relative recovery score
    that is directly comparable to a resting readiness score.

    This score is **distinct** from :func:`orthostatic_score`, which measures
    the quality of the autonomic response to standing (ΔHR + HF withdrawal).
    Together they capture two orthogonal dimensions of the same session:

    * ``orthostatic_readiness_score`` → *"Am I well recovered today?"* (relative)
    * ``orthostatic_score``           → *"Is my autonomic response healthy?"* (absolute)

    Args:
        supine: HRV features of the supine phase (``OrthostaticRecord.supine``
            or ``result.phases.supine.features``).
        baseline: Personal reference built from previous supine sessions.
            Returns 50.0 (neutral) when empty.

    Returns:
        Readiness score in [0, 100]. 50 = neutral (equal to personal supine baseline).

    """
    return readiness_score_multi(supine, baseline)


def orthostatic_score(hr_response: float, hf_response_pct: float = 0.0) -> float:
    """Compute a composite autonomic score for the orthostatic (tilt) test.

    The score combines two validated autonomic markers:

    * **ΔHR component (80 %)** — HR increase from supine baseline to
      stabilised standing position.  The optimal physiological range is 10–25
      bpm; below 5 bpm indicates an impaired sympathetic response, above 30
      bpm meets the POTS (Postural Orthostatic Tachycardia Syndrome) criterion.
    * **HF vagal-withdrawal component (20 %)** — relative drop in HF spectral
      power on standing.  A drop of −30 % to −60 % reflects normal vagal
      withdrawal; outside this range the component score is reduced.

    ΔHR calibration:

    | ΔHR (bpm)  | Category             | Approximate score |
    | ---------- | -------------------- | ----------------- |
    | < 5        | Severely impaired    | < 20              |
    | 5 – 10     | Borderline low       | 20 – 65           |
    | 10 – 25    | Normal (optimal)     | 65 – 100          |
    | 25 – 30    | Borderline elevated  | 40 – 65           |
    | > 30       | Elevated (POTS)      | < 30              |

    HF withdrawal calibration:

    | hf_response_pct | Category                  | HF sub-score |
    | --------------- | ------------------------- | ------------ |
    | −60 % to −30 %  | Normal vagal withdrawal   | 1.0          |
    | 0 % to −30 %    | Insufficient withdrawal   | 0 – 1.0      |
    | > 0 %           | Paradoxical (HF increase) | 0.0          |
    | < −60 %         | Excessive withdrawal      | 0 – 1.0      |

    References:
        Brignole, M., et al. (2018). 2018 ESC Guidelines for the diagnosis
        and management of syncope. *European Heart Journal*, 39(21), 1883–1948.

        Sheldon, R. S., et al. (2015). 2015 Heart Rhythm Society expert
        consensus statement on the diagnosis and treatment of postural
        tachycardia syndrome, inappropriate sinus tachycardia, and vasovagal
        syncope. *Heart Rhythm*, 12(6), e41–e63.

        Task Force of the European Society of Cardiology and the North
        American Society of Pacing and Electrophysiology (1996). Heart rate
        variability: standards of measurement, physiological interpretation,
        and clinical use. *Circulation*, 93(5), 1043–1065.

    Args:
        hr_response: HR increase from supine to stabilised standing (bpm).
            Negative values are treated as 0.
        hf_response_pct: Relative change in HF spectral power from supine to
            standing, in percent (typically negative — HF decreases on
            standing). Defaults to 0.0 when not available.

    Returns:
        Composite autonomic score in [0, 100].

    """
    # ── ΔHR component (piece-wise, U-shaped) ─────────────────────────────────
    # Local constants (lowercase to comply with PEP 8 / ruff N806)
    opt_low: float = 10.0  # lower bound of normal range (bpm)
    opt_high: float = 25.0  # upper bound of normal range (bpm)
    opt_ctr: float = 17.5  # midpoint — peak score (bpm)
    pots: float = 30.0  # POTS threshold (bpm)

    hr = max(hr_response, 0.0)

    if hr < opt_low:
        # Impaired zone: linear from 0 to 65 over [0, 10]
        hr_score: float = 65.0 * (hr / opt_low)
    elif hr <= opt_high:
        # Normal zone: 65–100, peak at centre
        deviation = abs(hr - opt_ctr) / (opt_high - opt_low) * 2.0
        hr_score = 100.0 - 35.0 * deviation
    elif hr <= pots:
        # Borderline high: linear from 65 at 25 bpm to 30 at 30 bpm
        t = (hr - opt_high) / (pots - opt_high)
        hr_score = 65.0 - 35.0 * t
    else:
        # POTS zone: exponential decay from 30 at 30 bpm
        hr_score = max(0.0, 30.0 * math.exp(-(hr - pots) / 5.0))

    # ── HF vagal-withdrawal component ────────────────────────────────────────
    # hf_response_pct is negative when HF power drops (normal direction).
    if hf_response_pct < -60.0:
        # Excessive withdrawal: linear from 1.0 at −60 % to 0 at −100 %
        excess = (-hf_response_pct - 60.0) / 40.0
        hf_sub: float = max(0.0, 1.0 - excess)
    elif hf_response_pct <= -30.0:
        # Normal range (−30 % to −60 %): full sub-score
        hf_sub = 1.0
    elif hf_response_pct < 0.0:
        # Insufficient withdrawal: linear from 0 to 1.0
        hf_sub = -hf_response_pct / 30.0
    else:
        # Paradoxical increase (HF went up on standing)
        hf_sub = 0.0

    # ── Weighted combination ──────────────────────────────────────────────────
    combined = 0.80 * hr_score + 0.20 * (hf_sub * 100.0)
    return float(np.clip(combined, 0.0, 100.0))


# ======================
# SESSION SCORE (one entry point per protocol)
# ======================

SCORED_PROTOCOLS: tuple[str, ...] = (
    "resting",
    "orthostatic",
    "coherence",
    "hrr",
    "drift",
    "vo2max",
)
"""Protocols handled by :func:`session_score`."""


def session_score(protocol: str, result, baseline: Baseline | None = None) -> float:
    """Return the [0–100] score stored with a session of ``protocol``.

    Single entry point used when a session is saved or reprocessed:

    * ``resting`` — :func:`readiness_score_multi` against ``baseline`` (the
      previous sessions); 50 (neutral) without baseline.
    * ``orthostatic`` — :func:`orthostatic_score` (ΔHR + HF withdrawal).
    * ``coherence`` — :func:`coherence_score_100`.
    * ``hrr`` — :func:`hrr_score` on HRR at 60 s.
    * ``drift`` — :func:`drift_score`.
    * ``vo2max`` — :func:`vo2max_score` on the Uth estimate when available,
      otherwise the indicative ln-RMSSD estimate, against the norms of the
      result's ``age`` and ``sex`` when set.

    Args:
        protocol: One of :data:`SCORED_PROTOCOLS`.
        result: Protocol result (``HRVFeatures``, ``OrthostaticResult``, …).
        baseline: Personal baseline, used for ``resting`` only.

    Returns:
        Score in [0, 100].

    Raises:
        ValueError: If ``protocol`` is unknown.

    """
    if protocol == "resting":
        if baseline is None or not baseline.sessions:
            return 50.0
        return readiness_score_multi(result, baseline)
    if protocol == "orthostatic":
        return orthostatic_score(result.hr_response, result.hf_response_pct)
    if protocol == "coherence":
        return coherence_score_100(result.coherence_score)
    if protocol == "hrr":
        return hrr_score(result.hrr_60)
    if protocol == "drift":
        return drift_score(result.drift_rate)
    if protocol == "vo2max":
        return vo2max_score(
            result.best_estimate,
            getattr(result, "age", None),
            getattr(result, "sex", None),
        )
    raise ValueError(
        f"Unknown protocol {protocol!r}. Choose from {', '.join(SCORED_PROTOCOLS)}."
    )
