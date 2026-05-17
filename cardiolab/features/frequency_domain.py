"""Frequency-domain HRV metrics computed via Welch's power spectral density."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch


def frequency_domain(rr, fs: float = 4.0) -> dict:
    """Compute frequency-domain HRV metrics using Welch's method.

    The RR interval series is first linearly interpolated onto a uniform time
    grid at ``fs`` Hz. The Power Spectral Density (PSD) is then estimated with
    Welch's method and integrated over three physiological frequency bands:

    * **VLF** (0.003 – 0.04 Hz): very-low-frequency power, linked to
      thermoregulation and hormonal activity.
    * **LF** (0.04 – 0.15 Hz): low-frequency power, reflecting a mix of
      sympathetic and parasympathetic modulation.
    * **HF** (0.15 – 0.40 Hz): high-frequency power, driven by respiratory
      sinus arrhythmia and considered a marker of parasympathetic activity.

    Args:
        rr: An ``RRSeries`` instance. Must contain enough intervals to cover
            at least one Welch segment (length ≥ 256 samples after interpolation
            is recommended for reliable spectral estimates).
        fs: Interpolation and analysis sampling frequency in Hz.
            Defaults to 4.0 Hz (HRV standard minimum for HF band coverage).

    Returns:
        Dictionary with the following keys (absolute powers in ms²):

        * ``"VLF"``        — absolute VLF power (ms²). Typical resting range: 300–3 000 ms².
        * ``"LF"``         — absolute LF power (ms²). Typical resting range: 200–2 000 ms².
        * ``"HF"``         — absolute HF power (ms²). Typical resting range: 200–2 000 ms².
        * ``"TP"``         — total power VLF + LF + HF (ms²).
        * ``"LF_HF"``      — LF/HF ratio (0.0 if HF is zero).
        * ``"LF_nu"``      — LF in normalised units: LF / (LF + HF).
        * ``"HF_nu"``      — HF in normalised units: HF / (LF + HF).
        * ``"HF_pct"``     — HF as a fraction of total power.
        * ``"LF_pct"``     — LF as a fraction of total power.
        * ``"LF_HF_sum"``  — LF + HF combined power (ms²).
        * ``"LF_HF_over_TP"`` — (LF + HF) / TP ratio.

    """
    rr_ms = np.array(
        rr.intervals
    )  # ms — kept in ms so PSD is in ms²/Hz → band power in ms²
    time_s = np.cumsum(rr_ms) / 1000.0  # seconds — for a Hz-correct frequency axis
    time_s = time_s - time_s[0]

    # ======================
    # Interpolation
    # ======================

    interp_time = np.arange(0, time_s[-1], 1 / fs)
    interp_rr = np.interp(interp_time, time_s, rr_ms)  # ms values on a uniform s grid

    # ======================
    # PSD estimation
    # ======================

    freqs, psd = welch(interp_rr, fs=fs, nperseg=min(256, len(interp_rr)))

    # ======================
    # Band power integration
    # ======================

    vlf = _band_power(freqs, psd, 0.003, 0.04)
    lf = _band_power(freqs, psd, 0.04, 0.15)
    hf = _band_power(freqs, psd, 0.15, 0.4)

    tp = vlf + lf + hf

    return {
        "VLF": vlf,
        "LF": lf,
        "HF": hf,
        "TP": tp,
        "LF_HF": lf / hf if hf > 0 else 0,
        "LF_nu": lf / (lf + hf) if (lf + hf) > 0 else 0,
        "HF_nu": hf / (lf + hf) if (lf + hf) > 0 else 0,
        "HF_pct": hf / tp if tp > 0 else 0,
        "LF_pct": lf / tp if tp > 0 else 0,
        "LF_HF_sum": lf + hf,
        "LF_HF_over_TP": (lf + hf) / tp if tp > 0 else 0,
    }


def _band_power(freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    """Integrate PSD over a frequency band using the trapezoidal rule.

    Args:
        freqs: Frequency axis returned by Welch's method (Hz).
        psd: Power spectral density values corresponding to ``freqs``.
        low: Lower bound of the integration band (Hz, inclusive).
        high: Upper bound of the integration band (Hz, exclusive).

    Returns:
        Band power as the area under the PSD curve within [``low``, ``high``].
        Returns 0.0 if the band contains no frequency bins.

    """
    mask = (freqs >= low) & (freqs < high)
    return float(np.trapezoid(psd[mask], freqs[mask]))
