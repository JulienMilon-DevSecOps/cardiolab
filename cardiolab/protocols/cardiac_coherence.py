"""Cardiac coherence 5-5 protocol: resonance breathing assessment.

Cardiac coherence (cohérence cardiaque) is assessed during a guided paced
breathing session — 5 s inspiration / 5 s expiration (6 breaths/min) for
at least 2–5 minutes. At this respiratory rate the autonomic nervous system
resonates near 0.1 Hz, producing a large sinusoidal RR oscillation and
maximal HRV power in the cardiac resonance band.

The coherence score quantifies how much of the resonance-band power (0.04–
0.26 Hz) concentrates around the dominant spectral peak:

    coherence_score = peak_window_power / total_resonance_power × 100

Higher scores reflect stronger rhythmic vagal modulation. A score above
60 % indicates good cardiac coherence.

References:
    Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback:
    how and why does it work? Frontiers in Psychology, 5, 756.

    McCraty, R., & Shaffer, F. (2015). Heart rate variability: new
    perspectives on physiological mechanisms, assessment of self-regulatory
    capacity, and health risk. Global Advances in Health and Medicine, 4(1),
    46–61.

"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.features.frequency_domain import _ar_psd
from cardiolab.features.time_domain import rmssd as _rmssd
from cardiolab.features.time_domain import sdnn as _sdnn
from cardiolab.signals.rr import RRSeries


@dataclass
class CoherenceResult:
    """Results from a cardiac coherence paced-breathing session.

    Attributes:
        date: ISO date string of the session.
        coherence_score: Percentage of resonance-band power concentrated at
            the dominant peak (0–100). Values ≥ 60 indicate good coherence.
        resonance_freq: Dominant frequency in the cardiac resonance band
            (0.04–0.26 Hz), in Hz. Expected near 0.1 Hz for 6 breaths/min.
        peak_power: Spectral power density at the resonance peak (ms²/Hz).
        total_power_resonance: Total power integrated over the resonance
            band 0.04–0.26 Hz (ms²).
        rmssd: RMSSD during the session (ms).
        sdnn: SDNN during the session (ms).
        mean_hr: Mean heart rate during the session (bpm).
        duration: Effective recording duration (s).

    """

    date: str | None = None
    coherence_score: float = 0.0
    resonance_freq: float = 0.0
    peak_power: float = 0.0
    total_power_resonance: float = 0.0
    rmssd: float = 0.0
    sdnn: float = 0.0
    mean_hr: float = 0.0
    duration: float = 0.0

    def to_dict(self) -> dict:
        """Return a flat dictionary of all result fields."""
        return {
            "date": self.date,
            "coherence_score": self.coherence_score,
            "resonance_freq": self.resonance_freq,
            "peak_power": self.peak_power,
            "total_power_resonance": self.total_power_resonance,
            "rmssd": self.rmssd,
            "sdnn": self.sdnn,
            "mean_hr": self.mean_hr,
            "duration": self.duration,
        }


def cardiac_coherence(
    rr: RRSeries,
    fs: float = 4.0,
    order: int = 16,
    resonance_low: float = 0.04,
    resonance_high: float = 0.26,
    peak_half_width: float = 0.015,
) -> CoherenceResult:
    """Assess cardiac coherence from a paced breathing session.

    Uses the AR (Yule-Walker) PSD method for spectral estimation — it gives
    better frequency resolution than Welch on short 2–5 min sessions.

    Coherence score interpretation:

    | Score (%) | Interpretation                        |
    | --------- | ------------------------------------- |
    | ≥ 60      | Good cardiac coherence                |
    | 40 – 60   | Moderate — improve breathing cadence  |
    | < 40      | Low — poor vagal resonance            |

    Args:
        rr: RR interval series from a paced breathing session (≥ 30 beats,
            ideally ≥ 2 min / 120 beats for 5-5 breathing).
        fs: Resampling frequency in Hz. Defaults to 4.0 Hz.
        order: AR model order. Defaults to 16.
        resonance_low: Lower bound of the cardiac resonance band (Hz).
            Defaults to 0.04 Hz.
        resonance_high: Upper bound of the cardiac resonance band (Hz).
            Defaults to 0.26 Hz.
        peak_half_width: Half-width of the integration window centred on
            the spectral peak (Hz). Defaults to 0.015 Hz.

    Returns:
        CoherenceResult with coherence score, resonance frequency, power
        metrics, and basic HRV indicators.

    Raises:
        ValueError: If the series has fewer than 30 intervals.

    """
    if len(rr.intervals) < 30:
        raise ValueError(
            f"Too few RR intervals ({len(rr.intervals)}). "
            "At least 30 beats are required for coherence analysis."
        )

    rr_ms = np.array(rr.intervals, dtype=float)
    time_s = np.cumsum(rr_ms) / 1000.0
    time_s -= time_s[0]

    interp_time = np.arange(0, time_s[-1], 1.0 / fs)
    interp_rr = np.interp(interp_time, time_s, rr_ms)

    try:
        freqs, psd = _ar_psd(interp_rr, fs=fs, order=order)
    except Exception:
        # Degenerate signal (constant or near-constant) — return empty result
        mean_rr = float(np.mean(rr_ms))
        mean_hr = 60_000.0 / mean_rr if mean_rr > 0 else 0.0
        return CoherenceResult(
            mean_hr=mean_hr,
            duration=float(time_s[-1]) if len(time_s) > 0 else 0.0,
        )

    mask_band = (freqs >= resonance_low) & (freqs < resonance_high)
    if np.any(mask_band):
        band_f = freqs[mask_band]
        band_p = psd[mask_band]
        peak_idx = int(np.argmax(band_p))
        resonance_freq = float(band_f[peak_idx])
        peak_power = float(band_p[peak_idx])
        total_resonance = float(np.trapezoid(band_p, band_f))

        lo = resonance_freq - peak_half_width
        hi = resonance_freq + peak_half_width
        mask_peak = (freqs >= lo) & (freqs <= hi)
        n_peak = int(np.sum(mask_peak))
        if n_peak >= 2:
            peak_window_power = float(np.trapezoid(psd[mask_peak], freqs[mask_peak]))
        elif n_peak == 1:
            # Only one bin in window — use rectangular integration (bin width = df)
            df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
            peak_window_power = float(np.sum(psd[mask_peak])) * df
        else:
            # Window narrower than one bin: use the peak bin alone
            df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
            peak_window_power = peak_power * df

        coherence_score = (
            min(peak_window_power / total_resonance * 100.0, 100.0)
            if total_resonance > 0.0
            else 0.0
        )
    else:
        resonance_freq = 0.0
        peak_power = 0.0
        total_resonance = 0.0
        coherence_score = 0.0

    mean_rr = float(np.mean(rr_ms))
    mean_hr = 60_000.0 / mean_rr if mean_rr > 0 else 0.0

    return CoherenceResult(
        coherence_score=coherence_score,
        resonance_freq=resonance_freq,
        peak_power=peak_power,
        total_power_resonance=total_resonance,
        rmssd=float(_rmssd(rr)),
        sdnn=float(_sdnn(rr)),
        mean_hr=mean_hr,
        duration=float(time_s[-1]) if len(time_s) > 0 else 0.0,
    )
