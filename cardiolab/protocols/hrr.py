"""Heart Rate Recovery (HRR) protocol: post-exercise vagal reactivation.

Heart Rate Recovery measures the speed at which heart rate declines after
maximal or submaximal exercise. The drop in HR during the first minute
post-exercise (HRR1) is a marker of parasympathetic reactivation and is
strongly associated with cardiovascular mortality risk.

The protocol requires a continuous RR series recorded from peak effort through
at least 2 minutes of passive recovery:

    HRR1 = HR_peak − HR_at_60s
    HRR2 = HR_peak − HR_at_120s

HR values are **medians over 5 s**, never read on a single beat: HR_peak is the
highest 5-s median of the first 15 s, HR_at_60s / HR_at_120s the median HR
between 57.5–62.5 s / 117.5–122.5 s — one artefact or ectopic beat in a window
does not move it. Changed in 0.5.0: HR_peak was the HR of the very
first beat and HR_at_60s a single interpolated point — one artefact or ectopic
beat (the series is analysed as recorded) shifted HRR1 by 10 bpm or more.

Categories (HRR1, Cole et al. 1999):

| HRR1 (bpm) | Category   |
| ---------- | ---------- |
| ≥ 25       | Excellent  |
| 20 – 24    | Good       |
| 12 – 19    | Normal     |
| < 12       | Impaired   |

A HRR1 < 12 bpm is an independent predictor of all-cause mortality.

References:
    Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., &
    Lauer, M. S. (1999). Heart-rate recovery immediately after exercise as a
    predictor of mortality. New England Journal of Medicine, 341(18),
    1351–1357.

    Imai, K., Sato, H., Hori, M., et al. (1994). Vagally mediated heart rate
    recovery after exercise is accelerated in athletes but blunted in patients
    with chronic heart failure. Journal of the American College of Cardiology,
    24(6), 1529–1535.

"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np

from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

SMOOTH_SEC = 5.0
"""Window of the HR values (s) — median of the beats it contains."""

PEAK_SEARCH_SEC = 15.0
"""The peak HR is searched in the first seconds of the recording."""


def _mean_hr(time_s: np.ndarray, hr: np.ndarray, centre: float) -> float:
    """Median HR of the beats within ``centre ± SMOOTH_SEC / 2`` (nearest beat if none)."""
    half = SMOOTH_SEC / 2.0
    mask = (time_s >= centre - half) & (time_s <= centre + half)
    if not np.any(mask):
        return float(hr[int(np.argmin(np.abs(time_s - centre)))])
    return float(np.median(hr[mask]))


def _peak_hr(time_s: np.ndarray, hr: np.ndarray) -> float:
    """Highest 5-s median HR whose window starts within the first ``PEAK_SEARCH_SEC``."""
    starts = time_s[time_s <= PEAK_SEARCH_SEC - SMOOTH_SEC]
    if starts.size == 0:
        starts = time_s[:1]
    return max(
        float(np.median(hr[(time_s >= s) & (time_s < s + SMOOTH_SEC)])) for s in starts
    )


def _categorise_hrr1(hrr1: float) -> str:
    if hrr1 >= 25:
        return "excellent"
    if hrr1 >= 20:
        return "good"
    if hrr1 >= 12:
        return "normal"
    return "impaired"


def _categorise_hrr2(hrr2: float) -> str:
    if hrr2 >= 55:
        return "excellent"
    if hrr2 >= 45:
        return "good"
    if hrr2 >= 35:
        return "normal"
    return "impaired"


@dataclass
class HRRResult:
    """Results from a Heart Rate Recovery session.

    Attributes:
        date: ISO date string of the session.
        hr_peak: Peak heart rate at the end of exercise — highest 5-s median
            of the first 15 s (bpm).
        hr_at_60s: Median heart rate between 57.5 and 62.5 s (bpm).
        hr_at_120s: Median heart rate between 117.5 and 122.5 s (bpm).
            Set to ``nan`` if the recording is shorter than 120 s.
        hrr_60: HR drop at 60 s: ``hr_peak − hr_at_60s`` (bpm).
        hrr_120: HR drop at 120 s: ``hr_peak − hr_at_120s`` (bpm).
            Set to ``nan`` if the recording is shorter than 120 s.
        hrr_60_category: Clinical category for HRR1
            (``"excellent"`` / ``"good"`` / ``"normal"`` / ``"impaired"``).
        hrr_120_category: Clinical category for HRR2 (same levels as HRR1,
            different thresholds). Empty string if HRR2 is unavailable.
        duration: Total recording duration from peak to end (s).

    """

    date: str | None = None
    hr_peak: float = 0.0
    hr_at_60s: float = 0.0
    hr_at_120s: float = float("nan")
    hrr_60: float = 0.0
    hrr_120: float = float("nan")
    hrr_60_category: str = ""
    hrr_120_category: str = ""
    duration: float = 0.0
    score: float = 0.0

    def to_dict(self) -> dict:
        """Return a flat dictionary of all result fields."""
        return {
            "date": self.date,
            "hr_peak": self.hr_peak,
            "hr_at_60s": self.hr_at_60s,
            "hr_at_120s": self.hr_at_120s,
            "hrr_60": self.hrr_60,
            "hrr_120": self.hrr_120,
            "hrr_60_category": self.hrr_60_category,
            "hrr_120_category": self.hrr_120_category,
            "duration": self.duration,
            "score": self.score,
        }


def heart_rate_recovery(
    rr: RRSeries,
    fs: float | None = None,
) -> HRRResult:
    """Compute Heart Rate Recovery metrics from a post-exercise RR series.

    The RR series must start at or immediately after exercise termination
    (t = 0). HR values are medians over 5 s: the peak is the highest 5-s
    median of the first 15 s, HR at 60 s / 120 s the median around t = 60 s
    / 120 s.

    HRR1 interpretation:

    | HRR1 (bpm) | Category  | Risk                              |
    | ---------- | --------- | --------------------------------- |
    | ≥ 25       | Excellent | Very low cardiovascular risk      |
    | 20 – 24    | Good      | Low risk                          |
    | 12 – 19    | Normal    | Average risk                      |
    | < 12       | Impaired  | Elevated mortality risk (×2 RR)   |

    Args:
        rr: Post-exercise RR interval series. The series must start at peak
            effort and contain at least 30 intervals (≈ 60 s recovery).
        fs: Ignored — kept for compatibility (HR is no longer resampled).

    Returns:
        ``HRRResult`` with HRR1, HRR2 (when available), HR values, and
        clinical categories.

    Raises:
        ValueError: If the series has fewer than 30 intervals.

    """
    if len(rr.intervals) < 30:
        raise ValueError(
            f"Too few RR intervals ({len(rr.intervals)}). "
            "At least 30 are required for HRR analysis."
        )

    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    time_s -= time_s[0]
    duration = float(time_s[-1])

    if duration < 120.0:
        warnings.warn(
            f"HRR recording duration ({duration:.0f} s) is below 120 s. "
            "HRR2 (2-minute recovery) cannot be computed and will be set to 0. "
            "Extend the recording to at least 120 s for a complete HRR assessment.",
            PhysiologicalWarning,
            stacklevel=2,
        )

    # Instantaneous HR of each beat (bpm), summarised by 5-s medians below
    hr_inst = 60_000.0 / rr_ms

    hr_peak = _peak_hr(time_s, hr_inst)

    # HR at 60 s — the last 5 s when the recording is shorter
    hr_at_60 = _mean_hr(time_s, hr_inst, min(60.0, duration - SMOOTH_SEC / 2.0))
    hrr_60 = hr_peak - hr_at_60

    # HR at 120 s (optional)
    if duration >= 120.0:
        hr_at_120 = _mean_hr(time_s, hr_inst, 120.0)
        hrr_120 = hr_peak - hr_at_120
        hrr_120_cat = _categorise_hrr2(hrr_120)
    else:
        hr_at_120 = float("nan")
        hrr_120 = float("nan")
        hrr_120_cat = ""

    return HRRResult(
        hr_peak=hr_peak,
        hr_at_60s=hr_at_60,
        hr_at_120s=hr_at_120,
        hrr_60=hrr_60,
        hrr_120=hrr_120,
        hrr_60_category=_categorise_hrr1(hrr_60),
        hrr_120_category=hrr_120_cat,
        duration=duration,
    )
