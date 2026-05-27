"""VO2max estimation from HRV and heart rate indices.

Two complementary regression models are provided:

1. **Uth et al. (2004)** — simple ratio model requiring resting and maximal HR:

       VO2max ≈ 15.3 × (HRmax / HRrest)

   This model is valid for healthy adults (18–65 y). Accuracy: ±10–15 %.

2. **Esco & Flatt (2014)** — RMSSD-based model using a resting HRV measurement:

       VO2max ≈ 18.37 + 0.054 × RMSSD

   Validated in recreationally active adults. Accuracy: ±7–12 %.
   An improved variant using ln(RMSSD) is also provided:

       VO2max ≈ 24.89 + 5.97 × ln(RMSSD)

   (Nunan et al. 2010, extended by Esco & Flatt 2014).

Both estimates are expressed in mL/kg/min. They are population-level
predictions and should not replace a laboratory VO2max test for clinical
decision-making.

Fitness categories (general adult population, ACSM 2022):

| VO2max (mL/kg/min) | Category    |
| ------------------ | ----------- |
| < 28               | Poor        |
| 28 – 37            | Fair        |
| 38 – 47            | Good        |
| 48 – 57            | Very good   |
| ≥ 58               | Excellent   |

References:
    Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004).
    Estimation of VO2max from the ratio between HRmax and HRrest — the
    Heart Rate Ratio Method. European Journal of Applied Physiology, 91(1),
    111–115.

    Esco, M. R., & Flatt, A. A. (2014). Ultra-short-term heart rate variability
    indices for gender identification and automatic prediction of cardiorespiratory
    fitness. Sensors, 14(3), 3934–3952.

    Nunan, D., Donovan, G., Jakovljevic, D. G., Hodges, L. D., Sandercock, G. R.,
    & Brodie, D. A. (2010). Validity and reliability of short-term heart-rate
    variability from the Polar S810. Medicine & Science in Sports & Exercise,
    42(2), 243–250.

    American College of Sports Medicine. (2022). ACSM's Guidelines for Exercise
    Testing and Prescription (11th ed.). Lippincott Williams & Wilkins.

"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from cardiolab.features.time_domain import rmssd as _rmssd
from cardiolab.signals.rr import RRSeries


def _fitness_category(vo2max: float) -> str:
    """Return ACSM fitness category from a VO2max estimate (mL/kg/min)."""
    if vo2max < 28:
        return "poor"
    if vo2max < 38:
        return "fair"
    if vo2max < 48:
        return "good"
    if vo2max < 58:
        return "very_good"
    return "excellent"


@dataclass
class VO2maxResult:
    """Results from a VO2max estimation session.

    Attributes:
        date: ISO date string of the measurement.
        vo2max_uth: VO2max estimate from Uth et al. (2004) — requires HR_max
            and HR_rest (mL/kg/min). ``nan`` if ``hr_max`` was not provided.
        vo2max_esco_flatt: VO2max estimate from Esco & Flatt (2014) using
            RMSSD (mL/kg/min).
        vo2max_ln_rmssd: VO2max estimate from the ln(RMSSD) variant
            (Nunan/Esco-Flatt extended model, mL/kg/min).
        hr_rest: Resting heart rate derived from the RR series (bpm).
        hr_max: Maximal heart rate provided by the user (bpm).
            ``nan`` if not provided.
        rmssd_used: RMSSD computed from the RR series (ms).
        ln_rmssd_used: Natural log of the RMSSD (dimensionless).
        fitness_category: ACSM fitness category derived from the best
            available estimate. Priority: Uth → Esco-Flatt → ln-RMSSD.

    """

    date: str | None = None
    vo2max_uth: float = float("nan")
    vo2max_esco_flatt: float = 0.0
    vo2max_ln_rmssd: float = 0.0
    hr_rest: float = 0.0
    hr_max: float = float("nan")
    rmssd_used: float = 0.0
    ln_rmssd_used: float = 0.0
    fitness_category: str = "poor"
    score: float = 0.0

    def to_dict(self) -> dict:
        """Return a flat dictionary of all result fields."""
        return {
            "date": self.date,
            "vo2max_uth": self.vo2max_uth,
            "vo2max_esco_flatt": self.vo2max_esco_flatt,
            "vo2max_ln_rmssd": self.vo2max_ln_rmssd,
            "hr_rest": self.hr_rest,
            "hr_max": self.hr_max,
            "rmssd_used": self.rmssd_used,
            "ln_rmssd_used": self.ln_rmssd_used,
            "fitness_category": self.fitness_category,
            "score": self.score,
        }


def vo2max_from_hrv(
    rr: RRSeries,
    hr_max: float | None = None,
) -> VO2maxResult:
    """Estimate VO2max from a resting HRV recording.

    Computes RMSSD, ln(RMSSD), and resting HR from ``rr``, then applies:

    * **Esco & Flatt (2014)**: ``VO2max ≈ 18.37 + 0.054 × RMSSD``
    * **ln-RMSSD variant**: ``VO2max ≈ 24.89 + 5.97 × ln(RMSSD)``
    * **Uth et al. (2004)**: ``VO2max ≈ 15.3 × (HRmax / HRrest)``
      (only when ``hr_max`` is provided)

    For the fitness category, the Uth model takes priority when available,
    otherwise the Esco-Flatt RMSSD estimate is used.

    Args:
        rr: Resting RR series (ideally ≥ 5 min, lying or seated position).
            At least 30 intervals are required.
        hr_max: Maximal heart rate (bpm), measured during a VO2max test or
            estimated (e.g. 220 − age). If ``None``, the Uth model is
            skipped and ``vo2max_uth`` is set to ``nan``.

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

    # Esco & Flatt (2014) — RMSSD model
    vo2_ef = 18.37 + 0.054 * rmssd_val

    # ln-RMSSD variant (Nunan / Esco-Flatt extended)
    vo2_ln = 24.89 + 5.97 * ln_rmssd_val

    # Uth et al. (2004) — HR ratio model
    if hr_max is not None and hr_max > 0 and hr_rest > 0:
        vo2_uth = 15.3 * (hr_max / hr_rest)
        best = vo2_uth
    else:
        vo2_uth = float("nan")
        best = vo2_ef

    category = _fitness_category(best)

    return VO2maxResult(
        vo2max_uth=vo2_uth,
        vo2max_esco_flatt=vo2_ef,
        vo2max_ln_rmssd=vo2_ln,
        hr_rest=hr_rest,
        hr_max=hr_max if hr_max is not None else float("nan"),
        rmssd_used=rmssd_val,
        ln_rmssd_used=ln_rmssd_val,
        fitness_category=category,
    )
