"""Cardiac coherence 5-5 protocol: resonance breathing assessment.

Cardiac coherence (cohérence cardiaque) is assessed during a guided paced
breathing session — 5 s inspiration / 5 s expiration (6 breaths/min) for
at least 2–5 minutes. At this respiratory rate the autonomic nervous system
resonates near 0.1 Hz, producing a large sinusoidal RR oscillation and
maximal HRV power in the cardiac resonance band.

The coherence score is the share of the **whole HRV spectrum** (0.0033–0.4
Hz) concentrated in a 0.030 Hz window around the highest peak of the 0.04–0.26
Hz range (McCraty & Shaffer 2015):

    coherence_score = peak_window_power / total_power × 100

It is the HeartMath coherence ratio ``CR = peak / (total − peak)`` expressed
as a percentage: ``score = CR / (1 + CR) × 100`` (:attr:`CoherenceResult.
coherence_ratio`). 50 % ⇔ CR = 1: the resonance peak holds as much power as
the rest of the spectrum.

Changed in 0.5.0: the denominator was the 0.04–0.26 Hz band only, and the
"peak" could be the lower edge of the band (VLF power leaking above 0.04 Hz)
— spontaneous breathing at rest scored ≈ 50–60 %, close to "good". It now
scores ≈ 20–30 %; scores of earlier versions are not comparable.

References:
    Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback:
    how and why does it work? Frontiers in Psychology, 5, 756.

    McCraty, R., & Shaffer, F. (2015). Heart rate variability: new
    perspectives on physiological mechanisms, assessment of self-regulatory
    capacity, and health risk. Global Advances in Health and Medicine, 4(1),
    46–61.

"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np

from cardiolab.features.frequency_domain import _ar_psd, _interpolate
from cardiolab.features.time_domain import rmssd as _rmssd
from cardiolab.features.time_domain import sdnn as _sdnn
from cardiolab.signals.quality import SignalQuality, quality_columns, signal_quality
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries


@dataclass
class CoherenceResult:
    """Results from a cardiac coherence paced-breathing session.

    Attributes:
        date: ISO date string of the session.
        coherence_score: Share of the whole spectrum (0.0033–0.4 Hz) in the
            0.030 Hz window of the resonance peak, in % (0–100). ≥ 50 % (CR ≥
            1) indicates good coherence.
        resonance_freq: Highest spectral peak (local maximum) in the 0.04–0.26
            Hz range, in Hz. Expected near 0.1 Hz for 6 breaths/min.
        peak_power: Spectral power density at the resonance peak (ms²/Hz).
        total_power_resonance: Total power integrated over the resonance
            band 0.04–0.26 Hz (ms²).
        rmssd: RMSSD during the session (ms).
        sdnn: SDNN during the session (ms).
        mean_hr: Mean heart rate during the session (bpm).
        duration: Effective recording duration (s).
        score: Readiness score on a **[0–100]** scale derived from the
            coherence score (Lehrer & Gevirtz 2014). Defaults to 0.0.
            Must be populated by ``coherence_score_100()`` before saving.
        quality: Signal quality index (see
            :func:`~cardiolab.signals.quality.signal_quality`). ``None`` when
            unknown (sessions stored before v0.4.0).

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
    score: float = 0.0
    quality: SignalQuality | None = None

    @property
    def coherence_ratio(self) -> float:
        """HeartMath coherence ratio ``peak / (total − peak)`` (McCraty & Shaffer 2015)."""
        share = self.coherence_score / 100.0
        return share / (1.0 - share) if share < 1.0 else math.inf

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
            "score": self.score,
            **quality_columns(self.quality),
        }


def cardiac_coherence(
    rr: RRSeries,
    fs: float = 4.0,
    order: int = 16,
    resonance_low: float = 0.04,
    resonance_high: float = 0.26,
    peak_half_width: float = 0.015,
    total_low: float = 0.0033,
    total_high: float = 0.4,
) -> CoherenceResult:
    """Assess cardiac coherence from a paced breathing session.

    Uses the AR (Yule-Walker) PSD method for spectral estimation — it gives
    better frequency resolution than Welch on short 2–5 min sessions.

    Coherence score interpretation (cardiolab thresholds, see the module
    docstring):

    | Score (%) | Coherence ratio | Interpretation                        |
    | --------- | --------------- | ------------------------------------- |
    | ≥ 50      | ≥ 1             | Good cardiac coherence                |
    | 30 – 50   | 0.43 – 1        | Moderate — improve breathing cadence  |
    | < 30      | < 0.43          | Low — spontaneous-breathing level     |

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
            the spectral peak (Hz). Defaults to 0.015 Hz (0.030 Hz window,
            McCraty & Shaffer 2015).
        total_low: Lower bound of the whole spectrum (Hz). Defaults to 0.0033.
        total_high: Upper bound of the whole spectrum (Hz). Defaults to 0.4.

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

    _min_recommended_sec = 120.0  # 2 min — ideally ≥ 5 min for 5-5 breathing
    if time_s[-1] < _min_recommended_sec:
        warnings.warn(
            f"Coherence recording duration ({time_s[-1]:.0f} s) is below the "
            f"recommended minimum of {_min_recommended_sec:.0f} s (2 min). "
            "The coherence score may be unreliable.",
            PhysiologicalWarning,
            stacklevel=2,
        )

    _, interp_rr = _interpolate(rr, fs)

    try:
        freqs, psd = _ar_psd(interp_rr, fs=fs, order=order)
    except Exception:
        # Degenerate signal (constant or near-constant) — return empty result
        mean_rr = float(np.mean(rr_ms))
        mean_hr = 60_000.0 / mean_rr if mean_rr > 0 else 0.0
        return CoherenceResult(
            mean_hr=mean_hr,
            duration=float(time_s[-1]) if len(time_s) > 0 else 0.0,
            quality=signal_quality(rr),
        )

    mask_band = (freqs >= resonance_low) & (freqs < resonance_high)
    mask_total = (freqs >= total_low) & (freqs <= total_high)
    total_power = (
        float(np.trapezoid(psd[mask_total], freqs[mask_total]))
        if np.sum(mask_total) >= 2
        else 0.0
    )
    if np.any(mask_band):
        band_idx = np.flatnonzero(mask_band)
        # Highest local maximum of the band — not its edge, where VLF power
        # decreasing above 0.04 Hz would otherwise be taken for a "peak"
        local = [
            i
            for i in band_idx
            if 0 < i < len(psd) - 1 and psd[i] > psd[i - 1] and psd[i] >= psd[i + 1]
        ]
        peak_idx = (
            max(local, key=lambda i: psd[i])
            if local
            else int(band_idx[np.argmax(psd[band_idx])])
        )
        resonance_freq = float(freqs[peak_idx])
        peak_power = float(psd[peak_idx])
        total_resonance = float(np.trapezoid(psd[band_idx], freqs[band_idx]))

        lo = resonance_freq - peak_half_width
        hi = resonance_freq + peak_half_width
        mask_peak = (freqs >= lo) & (freqs <= hi)
        n_peak = int(np.sum(mask_peak))
        df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
        if n_peak >= 2:
            peak_window_power = float(np.trapezoid(psd[mask_peak], freqs[mask_peak]))
        else:
            # Window narrower than the grid: rectangular integration of the peak bin
            peak_window_power = peak_power * df

        coherence_score = (
            min(peak_window_power / total_power * 100.0, 100.0)
            if total_power > 0.0
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
        quality=signal_quality(rr),
    )
