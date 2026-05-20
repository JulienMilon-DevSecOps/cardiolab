"""Heart Rate Recovery (HRR) protocol: post-exercise vagal reactivation.

Heart Rate Recovery measures the speed at which heart rate declines after
maximal or submaximal exercise. The drop in HR during the first minute
post-exercise (HRR1) is a marker of parasympathetic reactivation and is
strongly associated with cardiovascular mortality risk.

The protocol requires a continuous RR series recorded from peak effort through
at least 2 minutes of passive recovery. Heart rate is sampled at exactly 1 min
and 2 min post-peak:

    HRR1 = HR_peak − HR_at_60s
    HRR2 = HR_peak − HR_at_120s

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

from dataclasses import dataclass

import numpy as np

from cardiolab.signals.rr import RRSeries


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
        hr_peak: Peak heart rate at the end of exercise (bpm).
        hr_at_60s: Heart rate at exactly 60 s post-peak (bpm).
        hr_at_120s: Heart rate at exactly 120 s post-peak (bpm).
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
        }


def heart_rate_recovery(
    rr: RRSeries,
    fs: float = 4.0,
) -> HRRResult:
    """Compute Heart Rate Recovery metrics from a post-exercise RR series.

    The function assumes the **first beat of the series is the peak-effort
    beat** (i.e. the RR series must start at or immediately after exercise
    termination). HR is estimated from a 10-beat rolling average resampled at
    ``fs`` Hz, then sampled at t = 60 s and t = 120 s.

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
        fs: Resampling frequency for the interpolated HR curve (Hz).
            Defaults to 4.0 Hz.

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

    # Instantaneous HR from each RR interval (bpm)
    hr_inst = 60_000.0 / rr_ms

    # Resample to uniform grid
    interp_time = np.arange(0, time_s[-1], 1.0 / fs)
    hr_interp = np.interp(interp_time, time_s, hr_inst)

    # Peak HR = HR of the very first beat (start of recovery)
    hr_peak = float(hr_inst[0])

    # HR at 60 s
    idx_60 = int(60.0 * fs)
    if idx_60 < len(hr_interp):
        hr_at_60 = float(hr_interp[idx_60])
    else:
        # Recording shorter than 60 s — use last available point
        hr_at_60 = float(hr_interp[-1])

    hrr_60 = hr_peak - hr_at_60

    # HR at 120 s (optional)
    idx_120 = int(120.0 * fs)
    if idx_120 < len(hr_interp):
        hr_at_120 = float(hr_interp[idx_120])
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
