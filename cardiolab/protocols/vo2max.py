"""VO2max estimation from heart rate and HRV indices.

Two estimates are provided, in mL/kg/min:

1. **Uth et al. (2004)** — heart rate ratio model, the **reference** estimate:

       VO2max ≈ 15.3 × (HRmax / HRrest)

   Validated in healthy, trained men (Uth et al. 2004); accuracy ±10–15 %.
   ``hr_max`` is the athlete's maximal heart rate when known (measured or
   entered — ``hr_max_source = "provided"``). Otherwise, with the age, it is
   predicted with **Tanaka et al. (2001)**, ``208 − 0.7 × age``
   (``hr_max_source = "tanaka"``) — a population prediction (SD ≈ ±10 bpm),
   so the estimate is less precise than with a measured HRmax.

2. **ln-RMSSD model** — indicative estimate from resting HRV alone:

       VO2max ≈ 24.89 + 5.97 × ln(RMSSD)

   **No published source could be verified for this equation** — it is only
   used, as an indicative last resort, when neither ``hr_max`` nor the age is
   known. Resting HRV adds little to heart rate for predicting VO2max (Grant
   et al. 2013).

Removed in 0.4.0: the "Esco & Flatt (2014)" RMSSD model
(``18.37 + 0.054 × RMSSD``). It returned ≈ 20–24 mL/kg/min over the whole
normal RMSSD range, classing every user without ``hr_max`` as "poor" / "fair";
the cited paper (Esco & Flatt 2014) studies ultra-short HRV recordings and
contains no VO2max equation. ``vo2max_esco_flatt`` is kept for storage
compatibility and is always ``nan``.

These are population-level predictions; they do not replace a laboratory
VO2max test.

**Fitness categories by age and sex** (changed in 0.5.0) — percentiles of
the FRIEND registry (Kaminsky et al. 2015; 7 783 treadmill tests of healthy
US adults, the reference standards adopted by ACSM 2022), per decade from
20–29 to 70–79 (younger → 20–29, older → 70–79):

| Percentile of the athlete's sex and age | Category    |
| --------------------------------------- | ----------- |
| < 10th                                  | Poor        |
| 10th – 25th                             | Fair        |
| 25th – 75th                             | Good        |
| 75th – 90th                             | Very good   |
| ≥ 90th                                  | Excellent   |

The cut-offs are cardiolab's grouping of the FRIEND percentiles. Without age
and sex, the former fixed adult scale is used (< 28 poor, 28–37 fair, 38–47
good, 48–57 very good, ≥ 58 excellent mL/kg/min).

References:
    Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004).
    Estimation of VO2max from the ratio between HRmax and HRrest — the
    Heart Rate Ratio Method. European Journal of Applied Physiology, 91(1),
    111–115.

    Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal
    heart rate revisited. Journal of the American College of Cardiology,
    37(1), 153–156.

    Kaminsky, L. A., Arena, R., & Myers, J. (2015). Reference standards for
    cardiorespiratory fitness measured with cardiopulmonary exercise
    testing: data from the Fitness Registry and the Importance of Exercise
    National Database. Mayo Clinic Proceedings, 90(11), 1515–1523.

    Grant, C. C., Murray, C., Janse van Rensburg, D. C., & Fletcher, L.
    (2013). A comparison between heart rate and heart rate variability as
    indicators of cardiac health and fitness. Frontiers in Physiology, 4, 337.

    American College of Sports Medicine. (2022). ACSM's Guidelines for Exercise
    Testing and Prescription (11th ed.). Lippincott Williams & Wilkins.

"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from cardiolab.features.time_domain import rmssd as _rmssd
from cardiolab.signals.quality import SignalQuality, quality_columns, signal_quality
from cardiolab.signals.rr import RRSeries

FRIEND_PERCENTILES: dict[str, dict[int, tuple[float, ...]]] = {
    "male": {
        20: (32.1, 40.1, 48.0, 55.2, 61.8),
        30: (30.2, 35.9, 42.4, 49.2, 56.5),
        40: (26.8, 31.9, 37.8, 45.0, 52.1),
        50: (22.8, 27.1, 32.6, 39.7, 45.6),
        60: (19.8, 23.7, 28.2, 34.5, 40.3),
        70: (17.1, 20.4, 24.4, 30.4, 36.6),
    },
    "female": {
        20: (23.9, 30.5, 37.6, 44.7, 51.3),
        30: (20.9, 25.3, 30.2, 36.1, 41.4),
        40: (18.8, 22.1, 26.7, 32.4, 38.4),
        50: (17.3, 19.9, 23.4, 27.6, 32.0),
        60: (14.6, 17.2, 20.0, 23.8, 27.0),
        70: (13.6, 15.6, 18.3, 20.8, 23.1),
    },
}
"""VO2max (mL/kg/min) at the 10th, 25th, 50th, 75th and 90th percentiles,
by sex and age decade — FRIEND registry, treadmill (Kaminsky et al. 2015,
table 3)."""

_PERCENTILES = (10.0, 25.0, 50.0, 75.0, 90.0)
"""Percentiles of :data:`FRIEND_PERCENTILES`."""

_Z90 = 1.2815516
"""z-score of the 90th percentile of a normal distribution."""


def tanaka_hr_max(age: float) -> float:
    """Age-predicted maximal heart rate, ``208 − 0.7 × age`` (Tanaka et al. 2001).

    Args:
        age: Age in years.

    Returns:
        Predicted HRmax in bpm (SD ≈ ±10 bpm between individuals).

    """
    return 208.0 - 0.7 * age


def age_at(birth_year: int | None, date: str | None) -> int | None:
    """Age in years in the year of ``date`` (``None`` if either is missing).

    Args:
        birth_year: Year of birth (``user_profiles.birth_year``).
        date: ISO date of the measurement.

    Returns:
        ``year(date) − birth_year``, or ``None``.

    """
    if not birth_year or not date:
        return None
    return int(str(date)[:4]) - int(birth_year)


def _norms(age: float | None, sex: str | None) -> tuple[float, ...] | None:
    """FRIEND percentiles of the athlete's sex and age decade (``None`` if unknown)."""
    if age is None or sex not in FRIEND_PERCENTILES:
        return None
    decade = min(max(int(age) // 10 * 10, 20), 70)
    return FRIEND_PERCENTILES[sex][decade]


def vo2max_percentile(
    vo2max: float, age: float | None, sex: str | None
) -> float | None:
    """Percentile of a VO2max among people of the same sex and age decade.

    Linear interpolation between the 10th, 25th, 50th, 75th and 90th FRIEND
    percentiles (exact at those points); beyond the 10th / 90th, a normal tail
    whose SD matches that side of the distribution — (50th − 10th) / 1.28
    below, (90th − 50th) / 1.28 above.

    Args:
        vo2max: VO2max in mL/kg/min.
        age: Age in years.
        sex: ``"male"`` or ``"female"``.

    Returns:
        Percentile in [0, 100], or ``None`` without age, sex or a valid VO2max.

    """
    norms = _norms(age, sex)
    if norms is None or not math.isfinite(vo2max) or vo2max <= 0:
        return None
    p10, _, p50, _, p90 = norms
    if vo2max < p10 or vo2max > p90:
        sd = (p50 - p10 if vo2max < p10 else p90 - p50) / _Z90
        return 50.0 * (1.0 + math.erf((vo2max - p50) / sd / math.sqrt(2.0)))
    return float(np.interp(vo2max, norms, _PERCENTILES))


def vo2max_category(
    vo2max: float, age: float | None = None, sex: str | None = None
) -> str:
    """Fitness category of a VO2max (mL/kg/min).

    With age and sex: FRIEND percentiles of the same sex and age decade
    (< 10th poor, 10th–25th fair, 25th–75th good, 75th–90th very good,
    ≥ 90th excellent). Without them: the fixed adult scale.

    Args:
        vo2max: VO2max in mL/kg/min.
        age: Age in years.
        sex: ``"male"`` or ``"female"``.

    Returns:
        ``"poor"``, ``"fair"``, ``"good"``, ``"very_good"`` or ``"excellent"``.

    """
    norms = _norms(age, sex)
    cuts = norms[:2] + norms[3:] if norms else (28.0, 38.0, 48.0, 58.0)
    for cut, name in zip(cuts, ("poor", "fair", "good", "very_good"), strict=True):
        if vo2max < cut:
            return name
    return "excellent"


def _fitness_category(vo2max: float) -> str:
    """Return the category on the fixed adult scale (see :func:`vo2max_category`)."""
    return vo2max_category(vo2max)


@dataclass
class VO2maxResult:
    """Results from a VO2max estimation session.

    Attributes:
        date: ISO date string of the measurement.
        vo2max_uth: VO2max estimate from Uth et al. (2004) — requires HR_max
            and HR_rest (mL/kg/min). ``nan`` if ``hr_max`` was not provided.
        vo2max_esco_flatt: **Deprecated** — always ``nan`` since 0.4.0 (the
            RMSSD model was removed); kept for storage compatibility.
        vo2max_ln_rmssd: Indicative VO2max estimate from ln(RMSSD)
            (mL/kg/min) — no verified published source.
        hr_rest: Resting heart rate derived from the RR series (bpm).
        hr_max: Maximal heart rate used by the Uth model (bpm) — provided,
            or predicted from the age (Tanaka). ``nan`` if neither.
        hr_max_source: ``"provided"`` (given by the user), ``"tanaka"``
            (``208 − 0.7 × age``) or ``None`` (no HRmax — added in 0.5.0;
            ``None`` for rows stored before, where HRmax was always provided).
        rmssd_used: RMSSD computed from the RR series (ms).
        ln_rmssd_used: Natural log of the RMSSD (dimensionless).
        fitness_category: Fitness category of the best available estimate
            (Uth, otherwise the indicative ln-RMSSD estimate), against the
            FRIEND norms of the athlete's sex and age when known (changed in
            0.5.0 — fixed adult scale before).
        quality: Signal quality index of the resting recording (see
            :func:`~cardiolab.signals.quality.signal_quality`). ``None`` when
            unknown (estimations stored before v0.4.0).
        age: Age used for the norms and Tanaka (not stored).
        sex: Sex used for the norms (not stored).

    """

    date: str | None = None
    vo2max_uth: float = float("nan")
    vo2max_esco_flatt: float = float("nan")
    vo2max_ln_rmssd: float = 0.0
    hr_rest: float = 0.0
    hr_max: float = float("nan")
    hr_max_source: str | None = None
    rmssd_used: float = 0.0
    ln_rmssd_used: float = 0.0
    fitness_category: str = "poor"
    score: float = 0.0
    quality: SignalQuality | None = None
    age: int | None = None
    sex: str | None = None

    @property
    def best_estimate(self) -> float:
        """Uth estimate when available, otherwise the indicative ln-RMSSD one."""
        uth = self.vo2max_uth
        return uth if math.isfinite(uth) and uth > 0 else self.vo2max_ln_rmssd

    @property
    def percentile(self) -> float | None:
        """Percentile among people of the same sex and age (``None`` without them)."""
        return vo2max_percentile(self.best_estimate, self.age, self.sex)

    def to_dict(self) -> dict:
        """Return a flat dictionary of all result fields."""
        return {
            "date": self.date,
            "vo2max_uth": self.vo2max_uth,
            "vo2max_esco_flatt": self.vo2max_esco_flatt,
            "vo2max_ln_rmssd": self.vo2max_ln_rmssd,
            "hr_rest": self.hr_rest,
            "hr_max": self.hr_max,
            "hr_max_source": self.hr_max_source,
            "rmssd_used": self.rmssd_used,
            "ln_rmssd_used": self.ln_rmssd_used,
            "fitness_category": self.fitness_category,
            "score": self.score,
            **quality_columns(self.quality),
        }


def vo2max_from_hrv(
    rr: RRSeries,
    hr_max: float | None = None,
    *,
    age: int | None = None,
    sex: str | None = None,
) -> VO2maxResult:
    """Estimate VO2max from a resting HRV recording.

    Computes RMSSD, ln(RMSSD), and resting HR from ``rr``, then applies:

    * **Uth et al. (2004)**: ``VO2max ≈ 15.3 × (HRmax / HRrest)`` — the
      reference estimate. HRmax is ``hr_max`` when given, otherwise
      ``208 − 0.7 × age`` (Tanaka et al. 2001) when ``age`` is given;
    * **ln-RMSSD model**: ``VO2max ≈ 24.89 + 5.97 × ln(RMSSD)`` — indicative,
      no verified published source; used for the category only when there is
      neither ``hr_max`` nor ``age``.

    The category uses the FRIEND norms of ``sex`` and ``age`` when both are
    known (:func:`vo2max_category`).

    Changed in 0.5.0: Tanaka HRmax from the age, categories by age and sex.

    Args:
        rr: Resting RR series (ideally ≥ 5 min, lying or seated position).
            At least 30 intervals are required.
        hr_max: Maximal heart rate (bpm), measured or known by the athlete.
        age: Age in years (:func:`age_at` from ``birth_year``).
        sex: ``"male"`` or ``"female"``.

    Returns:
        ``VO2maxResult`` with all available estimates and a fitness category.

    Raises:
        ValueError: If the series has fewer than 30 intervals.

    """
    if len(rr.intervals) < 30:
        raise ValueError(
            f"Too few RR intervals ({len(rr.intervals)}). "
            "At least 30 are required for VO2max estimation."
        )

    rr_ms = np.array(rr.intervals, dtype=float)
    mean_rr = float(np.mean(rr_ms))
    hr_rest = 60_000.0 / mean_rr if mean_rr > 0 else 0.0

    rmssd_val = float(_rmssd(rr))
    ln_rmssd_val = math.log(rmssd_val) if rmssd_val > 0 else 0.0

    # ln-RMSSD model — indicative, no verified published source
    vo2_ln = 24.89 + 5.97 * ln_rmssd_val

    # HRmax: provided, otherwise predicted from the age (Tanaka et al. 2001)
    if hr_max is not None and math.isfinite(hr_max) and hr_max > 0:
        source = "provided"
    elif age is not None:
        hr_max, source = tanaka_hr_max(age), "tanaka"
    else:
        hr_max, source = None, None

    # Uth et al. (2004) — HR ratio model
    vo2_uth = 15.3 * (hr_max / hr_rest) if hr_max and hr_rest > 0 else float("nan")

    result = VO2maxResult(
        vo2max_uth=vo2_uth,
        vo2max_ln_rmssd=vo2_ln,
        hr_rest=hr_rest,
        hr_max=hr_max if hr_max is not None else float("nan"),
        hr_max_source=source,
        rmssd_used=rmssd_val,
        ln_rmssd_used=ln_rmssd_val,
        quality=signal_quality(rr),
        age=age,
        sex=sex,
    )
    result.fitness_category = vo2max_category(result.best_estimate, age, sex)
    return result
