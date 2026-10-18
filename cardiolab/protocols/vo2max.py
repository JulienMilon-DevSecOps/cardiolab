"""VO2max estimation from heart rate and HRV indices.

Two estimates are provided, in mL/kg/min:

1. **Uth et al. (2004)** — heart rate ratio model, the **reference** estimate:

       VO2max ≈ 15.3 × (HRmax / HRrest)

   Validated in healthy, trained men (Uth et al. 2004); accuracy ±10–15 %.
   Requires the maximal heart rate (``hr_max``).

2. **ln-RMSSD model** — indicative estimate from resting HRV alone:

       VO2max ≈ 24.89 + 5.97 × ln(RMSSD)

   **No published source could be verified for this equation** — it is kept
   as an indicative fallback when ``hr_max`` is unknown, and should be read
   with caution. Resting HRV adds little to heart rate for predicting VO2max
   (Grant et al. 2013).

Removed in 0.4.0: the "Esco & Flatt (2014)" RMSSD model
(``18.37 + 0.054 × RMSSD``). It returned ≈ 20–24 mL/kg/min over the whole
normal RMSSD range, classing every user without ``hr_max`` as "poor" / "fair";
the cited paper (Esco & Flatt 2014) studies ultra-short HRV recordings and
contains no VO2max equation. ``vo2max_esco_flatt`` is kept for storage
compatibility and is always ``nan``.

These are population-level predictions; they do not replace a laboratory
VO2max test.

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
        vo2max_esco_flatt: **Deprecated** — always ``nan`` since 0.4.0 (the
            RMSSD model was removed); kept for storage compatibility.
        vo2max_ln_rmssd: Indicative VO2max estimate from ln(RMSSD)
            (mL/kg/min) — no verified published source.
        hr_rest: Resting heart rate derived from the RR series (bpm).
        hr_max: Maximal heart rate provided by the user (bpm).
            ``nan`` if not provided.
        rmssd_used: RMSSD computed from the RR series (ms).
        ln_rmssd_used: Natural log of the RMSSD (dimensionless).
        fitness_category: ACSM fitness category derived from the best
            available estimate: Uth when ``hr_max`` is known, otherwise the
            indicative ln-RMSSD estimate (changed in 0.4.0 — was Esco-Flatt).
        quality: Signal quality index of the resting recording (see
            :func:`~cardiolab.signals.quality.signal_quality`). ``None`` when
            unknown (estimations stored before v0.4.0).

    """

    date: str | None = None
    vo2max_uth: float = float("nan")
    vo2max_esco_flatt: float = float("nan")
    vo2max_ln_rmssd: float = 0.0
    hr_rest: float = 0.0
    hr_max: float = float("nan")
    rmssd_used: float = 0.0
    ln_rmssd_used: float = 0.0
    fitness_category: str = "poor"
    score: float = 0.0
    quality: SignalQuality | None = None

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
            **quality_columns(self.quality),
        }


def vo2max_from_hrv(
    rr: RRSeries,
    hr_max: float | None = None,
) -> VO2maxResult:
    """Estimate VO2max from a resting HRV recording.

    Computes RMSSD, ln(RMSSD), and resting HR from ``rr``, then applies:

    * **Uth et al. (2004)**: ``VO2max ≈ 15.3 × (HRmax / HRrest)`` — the
      reference estimate, only when ``hr_max`` is provided;
    * **ln-RMSSD model**: ``VO2max ≈ 24.89 + 5.97 × ln(RMSSD)`` — indicative,
      no verified published source.

    The fitness category uses Uth when available, otherwise the ln-RMSSD
    estimate. Changed in 0.4.0: the Esco-Flatt RMSSD model is no longer
    computed (``vo2max_esco_flatt`` is ``nan``) — it classed every user
    without ``hr_max`` as "poor" / "fair".

    Args:
        rr: Resting RR series (ideally ≥ 5 min, lying or seated position).
            At least 30 intervals are required.
        hr_max: Maximal heart rate (bpm), measured during a VO2max test or
            estimated (208 − 0.7 × age, Tanaka et al. 2001). If ``None``, the Uth model is
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

    # ln-RMSSD model — indicative, no verified published source
    vo2_ln = 24.89 + 5.97 * ln_rmssd_val

    # Uth et al. (2004) — HR ratio model
    if hr_max is not None and hr_max > 0 and hr_rest > 0:
        vo2_uth = 15.3 * (hr_max / hr_rest)
        best = vo2_uth
    else:
        vo2_uth = float("nan")
        best = vo2_ln

    category = _fitness_category(best)

    return VO2maxResult(
        vo2max_uth=vo2_uth,
        vo2max_ln_rmssd=vo2_ln,
        hr_rest=hr_rest,
        hr_max=hr_max if hr_max is not None else float("nan"),
        rmssd_used=rmssd_val,
        ln_rmssd_used=ln_rmssd_val,
        fitness_category=category,
        quality=signal_quality(rr),
    )
