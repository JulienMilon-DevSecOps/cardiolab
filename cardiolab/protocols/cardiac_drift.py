"""Cardiac drift protocol: progressive HR increase at constant power output.

Cardiac drift (dérive cardiaque) is the gradual, progressive increase in heart
rate observed during prolonged exercise at constant workload, without any
increase in metabolic demand. It is caused by the combined effects of:

    * Dehydration — reduced plasma volume forces the heart to beat faster to
      maintain cardiac output.
    * Thermoregulation — blood is redistributed toward the skin for cooling,
      reducing central venous return.
    * Autonomic fatigue — progressive decline in parasympathetic tone.

The protocol captures continuous RR data during sustained exercise (typically
20–60 min at a constant wattage, pace, or % VO2max). The series is divided into
non-overlapping windows of ``window_sec`` seconds; the mean HR is computed in
each window, and linear regression of windowed HR over time yields:

    drift_rate: slope of the HR–time regression (bpm/min)
    drift_magnitude: total HR rise from first to last window (bpm)

Interpretation:

| Drift rate (bpm/min) | Category      |
| -------------------- | ------------- |
| < 0.5                | No drift      |
| 0.5 – 1.5            | Mild          |
| 1.5 – 3.0            | Moderate      |
| > 3.0                | Strong drift  |

A strong drift warrants hydration review and/or pacing adjustment.

References:
    Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift during
    prolonged exercise: new perspectives. Exercise and Sport Sciences Reviews,
    29(2), 88–92.

    Wingo, J. E., & Cureton, K. J. (2006). Cardiovascular responses to
    exercise with and without hydration. Medicine & Science in Sports &
    Exercise, 38(4), 739–748.

"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.signals.rr import RRSeries


def _interpret_drift(drift_rate: float) -> str:
    """Return a clinical drift category from the drift rate (bpm/min)."""
    if drift_rate < 0.5:
        return "no_drift"
    if drift_rate < 1.5:
        return "mild"
    if drift_rate < 3.0:
        return "moderate"
    return "strong"


@dataclass
class DriftResult:
    """Results from a cardiac drift analysis session.

    Attributes:
        date: ISO date string of the session.
        drift_rate: Slope of the linear HR regression over time (bpm/min).
            Positive values indicate upward drift; negative values may reflect
            progressive warm-up or recording artefact.
        drift_magnitude: Difference between the last and first window mean HR
            (bpm). Always a signed value.
        r_squared: Coefficient of determination (R²) of the linear fit.
            Values close to 1 indicate a clean, progressive drift.
        drift_detected: ``True`` when ``drift_rate ≥ 0.5 bpm/min``.
        initial_hr: Mean HR in the first window (bpm).
        final_hr: Mean HR in the last window (bpm).
        n_windows: Number of windows used for the regression.
        interpretation: Clinical category — ``"no_drift"``, ``"mild"``,
            ``"moderate"``, or ``"strong"``.
        duration: Total recording duration (s).

    """

    date: str | None = None
    drift_rate: float = 0.0
    drift_magnitude: float = 0.0
    r_squared: float = 0.0
    drift_detected: bool = False
    initial_hr: float = 0.0
    final_hr: float = 0.0
    n_windows: int = 0
    interpretation: str = "no_drift"
    duration: float = 0.0

    def to_dict(self) -> dict:
        """Return a flat dictionary of all result fields."""
        return {
            "date": self.date,
            "drift_rate": self.drift_rate,
            "drift_magnitude": self.drift_magnitude,
            "r_squared": self.r_squared,
            "drift_detected": self.drift_detected,
            "initial_hr": self.initial_hr,
            "final_hr": self.final_hr,
            "n_windows": self.n_windows,
            "interpretation": self.interpretation,
            "duration": self.duration,
        }


def cardiac_drift(
    rr: RRSeries,
    window_sec: float = 60.0,
) -> DriftResult:
    """Detect and quantify cardiac drift from a sustained-exercise RR series.

    Divides the series into non-overlapping windows of ``window_sec`` seconds,
    computes the mean HR in each window, then fits a linear regression of
    mean HR versus time. At least 3 windows are required.

    Drift rate interpretation:

    | Rate (bpm/min) | Category     | Action                              |
    | -------------- | ------------ | ----------------------------------- |
    | < 0.5          | No drift     | Normal thermoregulation             |
    | 0.5 – 1.5      | Mild         | Monitor hydration                   |
    | 1.5 – 3.0      | Moderate     | Drink soon, consider pace reduction |
    | > 3.0          | Strong drift | Stop or reduce intensity            |

    Args:
        rr: RR interval series recorded during constant-load exercise. The
            series must contain enough beats for at least 3 windows of
            ``window_sec`` seconds.
        window_sec: Window length for mean-HR estimation (s). Defaults to
            60 s, giving one data point per minute.

    Returns:
        ``DriftResult`` with drift rate, magnitude, R², detected flag,
        initial/final HR, window count, and interpretation.

    Raises:
        ValueError: If the recording is too short for at least 3 windows.

    """
    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    time_s -= time_s[0]
    duration = float(time_s[-1])

    # Build windows
    window_hrs: list[float] = []
    window_mid_times: list[float] = []
    t_start = 0.0

    while t_start + window_sec <= duration:
        t_end = t_start + window_sec
        mask = (time_s >= t_start) & (time_s < t_end)
        beats_in_window = rr_ms[mask]
        if len(beats_in_window) > 0:
            mean_rr_w = float(np.mean(beats_in_window))
            window_hrs.append(60_000.0 / mean_rr_w)
            window_mid_times.append(t_start + window_sec / 2.0)
        t_start += window_sec

    n_windows = len(window_hrs)
    if n_windows < 3:
        raise ValueError(
            f"Too few windows ({n_windows}). Need at least 3 windows of "
            f"{window_sec:.0f} s — record at least {3 * window_sec:.0f} s."
        )

    hr_arr = np.array(window_hrs)
    t_arr = np.array(window_mid_times) / 60.0  # convert to minutes

    # Linear regression
    coeffs = np.polyfit(t_arr, hr_arr, 1)
    drift_rate = float(coeffs[0])  # bpm/min

    # R²
    hr_pred = np.polyval(coeffs, t_arr)
    ss_res = float(np.sum((hr_arr - hr_pred) ** 2))
    ss_tot = float(np.sum((hr_arr - hr_arr.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    drift_magnitude = float(hr_arr[-1] - hr_arr[0])
    interpretation = _interpret_drift(abs(drift_rate))

    return DriftResult(
        drift_rate=drift_rate,
        drift_magnitude=drift_magnitude,
        r_squared=r_squared,
        drift_detected=abs(drift_rate) >= 0.5,
        initial_hr=float(hr_arr[0]),
        final_hr=float(hr_arr[-1]),
        n_windows=n_windows,
        interpretation=interpretation,
        duration=duration,
    )
