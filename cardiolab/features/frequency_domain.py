"""Frequency-domain HRV metrics via Welch's method or the AR (Yule-Walker) method."""

from __future__ import annotations

import numpy as np
from scipy.signal import welch

# ── Physiological frequency band definitions (Task Force ESC/NASPE 1996) ─────
# These are the authoritative constants for the whole package.
# Import them in other modules rather than redefining locally.

_VLF_BAND: tuple[float, float] = (0.003, 0.04)
"""Very-low-frequency band (Hz): thermoregulatory and hormonal influences."""

_LF_BAND: tuple[float, float] = (0.04, 0.15)
"""Low-frequency band (Hz): baroreflex, mixed sympathetic/parasympathetic."""

_HF_BAND: tuple[float, float] = (0.15, 0.40)
"""High-frequency band (Hz): respiratory sinus arrhythmia, vagal tone."""


def frequency_domain(
    rr,
    fs: float = 4.0,
    method: str = "welch",
    order: int = 16,
) -> dict:
    """Compute frequency-domain HRV metrics from an RR interval series.

    The RR interval series is first linearly interpolated onto a uniform time
    grid at ``fs`` Hz, then the Power Spectral Density (PSD) is estimated by
    the chosen method and integrated over three physiological frequency bands:

    * **VLF** (0.003 – 0.04 Hz): very-low-frequency power, linked to
      thermoregulation and hormonal activity.
    * **LF** (0.04 – 0.15 Hz): low-frequency power, reflecting a mix of
      sympathetic and parasympathetic modulation.
    * **HF** (0.15 – 0.40 Hz): high-frequency power, driven by respiratory
      sinus arrhythmia and considered a marker of parasympathetic activity.

    Two PSD methods are supported:

    * ``"welch"`` (default): Welch's periodogram — optimal for long recordings
      (≥ 5 min). Requires ≥ 256 interpolated samples for full resolution.
    * ``"ar"``: Autoregressive model (Yule-Walker, order ``order``) — better
      spectral resolution on short segments (< 2 min), recommended for the
      orthostatic transition phase.

    References:
        Task Force of ESC/NASPE (1996). Heart rate variability: Standards of
        measurement, physiological interpretation and clinical use.
        *Circulation*, 93(5), 1043–1065.

        Marple, S. L. (1987). *Digital Spectral Analysis with Applications*.
        Prentice-Hall.

    Args:
        rr: An ``RRSeries`` instance.
        fs: Interpolation and analysis sampling frequency in Hz.
            Defaults to 4.0 Hz.
        method: PSD estimation method — ``"welch"`` or ``"ar"``.
            Defaults to ``"welch"``.
        order: AR model order, used only when ``method="ar"``.
            Defaults to 16 (Task Force 1996 recommendation).

    Returns:
        Dictionary with the following keys (absolute powers in ms²):

        * ``"VLF"``           — absolute VLF power (ms²).
        * ``"LF"``            — absolute LF power (ms²).
        * ``"HF"``            — absolute HF power (ms²).
        * ``"TP"``            — total power VLF + LF + HF (ms²).
        * ``"LF_HF"``         — LF/HF ratio (0.0 if HF is zero).
        * ``"LF_nu"``         — LF in normalised units: LF / (LF + HF).
        * ``"HF_nu"``         — HF in normalised units: HF / (LF + HF).
        * ``"HF_pct"``        — HF as a fraction of total power.
        * ``"LF_pct"``        — LF as a fraction of total power.
        * ``"LF_HF_sum"``     — LF + HF combined power (ms²).
        * ``"LF_HF_over_TP"`` — (LF + HF) / TP ratio.

    Raises:
        ValueError: If ``method`` is not ``"welch"`` or ``"ar"``.

    """
    if method not in ("welch", "ar"):
        raise ValueError(f"Unknown method {method!r}. Choose 'welch' or 'ar'.")

    _, interp_rr = _interpolate(rr, fs)

    if method == "welch":
        freqs, psd = _welch_psd(interp_rr, fs)
    else:
        freqs, psd = _ar_psd(interp_rr, fs=fs, order=order)

    # ======================
    # Band power integration
    # ======================

    vlf = _band_power(freqs, psd, *_VLF_BAND)
    lf = _band_power(freqs, psd, *_LF_BAND)
    hf = _band_power(freqs, psd, *_HF_BAND)

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


def _interpolate(rr, fs: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Linearly interpolate an RRSeries onto a uniform time grid at ``fs`` Hz.

    Args:
        rr: An ``RRSeries`` instance.
        fs: Target sampling frequency in Hz.

    Returns:
        Tuple ``(t_interp, rr_interp)``: time axis (s) and interpolated RR (ms).

    """
    rr_ms = np.array(rr.intervals)
    t = np.cumsum(rr_ms) / 1000.0
    t = t - t[0]
    t_interp = np.arange(0, t[-1], 1.0 / fs)
    return t_interp, np.interp(t_interp, t, rr_ms)


def _welch_psd(signal: np.ndarray, fs: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(freqs, psd)`` using Welch's method on a uniformly sampled signal.

    Args:
        signal: Uniformly sampled RR signal (ms) on a regular time grid.
        fs: Sampling frequency in Hz.

    Returns:
        Tuple ``(freqs, psd)``: one-sided frequency axis (Hz) and PSD (ms²/Hz).

    """
    freqs, psd = welch(signal, fs=fs, nperseg=min(256, len(signal)))
    return freqs, psd


def _ar_psd(
    signal: np.ndarray,
    fs: float,
    order: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate one-sided PSD using the Yule-Walker autoregressive method.

    Solves the Yule-Walker equations (Levinson-Durbin, via scipy's
    ``solve_toeplitz``) to fit an AR(p) model of the given order, then
    evaluates the one-sided power spectral density on a 256-point frequency
    grid compatible with the Welch output from the same ``fs``.

    The one-sided convention doubles power in all bins except DC (0 Hz) and
    Nyquist (fs/2), ensuring that integrating with ``_band_power()`` yields
    band powers in ms² consistent with Welch's output.

    Args:
        signal: Uniformly sampled signal (ms values on a regular time grid).
        fs: Sampling frequency in Hz.
        order: AR model order. Internally clipped to ``min(order, N//2 - 1)``.

    Returns:
        Tuple ``(freqs, psd)``: one-sided frequency axis (Hz) and PSD (ms²/Hz).

    """
    from scipy.linalg import solve_toeplitz

    n = len(signal)
    x = signal - signal.mean()

    # Biased autocorrelation: R[k] = (1/N) Σ x[i] x[i+k]
    corr_full = np.correlate(x, x, mode="full")
    r = corr_full[n - 1 :] / n  # lags 0, 1, 2, ...

    safe_order = min(order, n // 2 - 1)

    r_col = r[:safe_order]  # first column of symmetric Toeplitz matrix
    r_rhs = r[1 : safe_order + 1]  # right-hand side: [R(1), …, R(p)]

    a_coeffs = solve_toeplitz(r_col, r_rhs)

    # Residual noise variance (prediction error power)
    sigma2 = max(r[0] - float(np.dot(a_coeffs, r_rhs)), 0.0)

    # 256-point one-sided PSD: P(f) = σ² / (fs · |A(f)|²)
    nfft = 256
    freqs = np.fft.rfftfreq(nfft, d=1.0 / fs)

    k = np.arange(1, safe_order + 1, dtype=float)
    exp_mat = np.exp(-2j * np.pi * freqs[:, np.newaxis] * k / fs)
    a_poly = 1.0 - exp_mat @ a_coeffs  # AR denominator polynomial A(f)

    psd = sigma2 / (fs * np.abs(a_poly) ** 2)
    psd[1:-1] *= 2.0  # one-sided: double all bins except DC and Nyquist

    return freqs, psd


def _band_power(freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    """Integrate PSD over a frequency band using the trapezoidal rule.

    Works identically for Welch and AR one-sided PSDs.

    Args:
        freqs: Frequency axis (Hz).
        psd: Power spectral density values corresponding to ``freqs``.
        low: Lower bound of the integration band (Hz, inclusive).
        high: Upper bound of the integration band (Hz, exclusive).

    Returns:
        Band power as the area under the PSD curve within [``low``, ``high``].
        Returns 0.0 if the band contains no frequency bins.

    """
    mask = (freqs >= low) & (freqs < high)
    return float(np.trapezoid(psd[mask], freqs[mask]))
