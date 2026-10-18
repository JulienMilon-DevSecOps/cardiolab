"""Frequency-domain HRV metrics — Welch, autoregressive (Yule-Walker) or Lomb-Scargle."""

from __future__ import annotations

import numpy as np
from scipy.signal import lombscargle, welch

# ── Physiological frequency band definitions (Task Force ESC/NASPE 1996) ─────
# These are the authoritative constants for the whole package.
# Import them in other modules rather than redefining locally.

_VLF_BAND: tuple[float, float] = (0.003, 0.04)
"""Very-low-frequency band (Hz): thermoregulatory and hormonal influences."""

_LF_BAND: tuple[float, float] = (0.04, 0.15)
"""Low-frequency band (Hz): baroreflex, mixed sympathetic/parasympathetic."""

_HF_BAND: tuple[float, float] = (0.15, 0.40)
"""High-frequency band (Hz): respiratory sinus arrhythmia, vagal tone."""

DEFAULT_WINDOW_SEC = 256.0
"""Welch segment length (s): frequency resolution 1/256 ≈ 0.004 Hz (Kubios-like)."""

VLF_MIN_DURATION_SEC = 300.0
"""Below this recording length, VLF power is flagged as unreliable."""

_LOMB_FMAX = 0.5
"""Upper frequency of the Lomb-Scargle grid (Hz) — covers the HF band."""

_AR_NFFT = 4096
"""FFT length of the AR PSD grid (≈ 0.001 Hz resolution at 4 Hz)."""


def frequency_domain(
    rr,
    fs: float = 4.0,
    method: str = "lomb",
    order: int = 16,
    window_sec: float = DEFAULT_WINDOW_SEC,
) -> dict:
    """Compute frequency-domain HRV metrics from an RR interval series.

    The Power Spectral Density (PSD) is estimated by the chosen method and
    integrated over three physiological frequency bands:

    * **VLF** (0.003 – 0.04 Hz): very-low-frequency power, linked to
      thermoregulation and hormonal activity.
    * **LF** (0.04 – 0.15 Hz): low-frequency power, reflecting a mix of
      sympathetic and parasympathetic modulation.
    * **HF** (0.15 – 0.40 Hz): high-frequency power, driven by respiratory
      sinus arrhythmia and considered a marker of parasympathetic activity.

    Three PSD methods are supported:

    * ``"lomb"`` (default): Lomb-Scargle periodogram computed directly on
      the beat times — **no interpolation**. On 5-minute recordings it gives
      the best trade-off between bias and session-to-session variability
      (see ``docs/features/frequency_domain.md``); also suited to irregular
      or gappy series (PPG, corrected artefacts).
    * ``"welch"``: Welch's periodogram on the RR series interpolated
      at ``fs`` Hz (cubic spline, :meth:`RRSeries.interpolate`), Hann
      segments of ``window_sec`` seconds (256 s → resolution ≈ 0.004 Hz) with
      50 % overlap and linear detrending. On a 5-minute recording this is a
      single 256-s segment, as in Kubios HRV.
    * ``"ar"``: Autoregressive model (Yule-Walker, order ``order``) on the
      same interpolated signal — smooth spectrum and better resolution on
      short segments (< 2 min), e.g. the orthostatic transition.

    Changed in 0.4.0: Welch used 64-s segments (``nperseg=256`` samples at
    4 Hz, resolution ≈ 0.016 Hz) on a linearly interpolated signal and was the
    default; ``lomb`` (now the default) and ``window_sec`` are new.

    References:
        Task Force of ESC/NASPE (1996). Heart rate variability: Standards of
        measurement, physiological interpretation and clinical use.
        *Circulation*, 93(5), 1043–1065.

        Marple, S. L. (1987). *Digital Spectral Analysis with Applications*.
        Prentice-Hall.

        Lomb, N. R. (1976). Least-squares frequency analysis of unequally
        spaced data. *Astrophysics and Space Science*, 39(2), 447–462.

        Tarvainen, M. P., et al. (2014). Kubios HRV — heart rate variability
        analysis software. *Computer Methods and Programs in Biomedicine*,
        113(1), 210–220.

    Args:
        rr: An ``RRSeries`` instance.
        fs: Interpolation and analysis sampling frequency in Hz.
            Defaults to 4.0 Hz.
        method: PSD estimation method — ``"welch"``, ``"ar"`` or
            ``"lomb"``. Defaults to ``"lomb"`` (changed in 0.4.0, was
            ``"welch"``).
        order: AR model order, used only when ``method="ar"``.
            Defaults to 16 (Task Force 1996 recommendation).
        window_sec: Welch segment length in seconds, used only when
            ``method="welch"``; bounded by the recording length.
            Defaults to 256 s.

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
        * ``"VLF_reliable"``  — ``False`` when the recording is shorter than
          5 minutes (:data:`VLF_MIN_DURATION_SEC`): the VLF band
          (periods of 25–333 s) cannot be estimated. Even at 5 minutes, the
          Task Force advises against interpreting VLF.

    Raises:
        ValueError: If ``method`` is not ``"welch"``, ``"ar"`` or ``"lomb"``.

    """
    if method not in ("welch", "ar", "lomb"):
        raise ValueError(f"Unknown method {method!r}. Choose 'welch', 'ar' or 'lomb'.")

    if method == "lomb":
        freqs, psd = _lomb_psd(rr)
    else:
        _, interp_rr = _interpolate(rr, fs)
        if method == "welch":
            freqs, psd = _welch_psd(interp_rr, fs, window_sec=window_sec)
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
        "VLF_reliable": bool(np.sum(rr.intervals) / 1000.0 >= VLF_MIN_DURATION_SEC),
    }


def _interpolate(rr, fs: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
    """Resample an RRSeries at ``fs`` Hz with the package-wide interpolation.

    Thin wrapper around :meth:`RRSeries.interpolate` (cubic spline) whose time
    axis starts at 0, as expected by the spectral functions and plots.

    Args:
        rr: An ``RRSeries`` instance.
        fs: Target sampling frequency in Hz.

    Returns:
        Tuple ``(t_interp, rr_interp)``: time axis (s, from 0) and RR (ms).

    """
    t_interp, rr_interp = rr.interpolate(fs)
    if len(t_interp):
        t_interp = t_interp - t_interp[0]
    return t_interp, rr_interp


def _welch_psd(
    signal: np.ndarray,
    fs: float = 4.0,
    window_sec: float = DEFAULT_WINDOW_SEC,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(freqs, psd)`` using Welch's method on a uniformly sampled signal.

    Hann segments of ``window_sec`` seconds (bounded by the signal length),
    50 % overlap, linear detrending of each segment.

    Args:
        signal: Uniformly sampled RR signal (ms) on a regular time grid.
        fs: Sampling frequency in Hz.
        window_sec: Segment length in seconds. Defaults to 256 s.

    Returns:
        Tuple ``(freqs, psd)``: one-sided frequency axis (Hz) and PSD (ms²/Hz).

    """
    nperseg = max(1, min(int(round(window_sec * fs)), len(signal)))
    freqs, psd = welch(
        signal, fs=fs, nperseg=nperseg, noverlap=nperseg // 2, detrend="linear"
    )
    return freqs, psd


def _lomb_psd(rr, fmax: float = _LOMB_FMAX) -> tuple[np.ndarray, np.ndarray]:
    """One-sided Lomb-Scargle PSD (ms²/Hz) computed on the beat times.

    No interpolation: each RR value is placed at its beat time
    (:meth:`RRSeries.beat_times`), after linear detrending. The unnormalised periodogram ``P`` is scaled
    like a classical periodogram, ``PSD = 2 · T · P / N`` (``T`` duration,
    ``N`` beats), so that integrating the PSD gives back the variance of the
    series (Parseval). The frequency grid is 4× oversampled (``1 / 4T``).

    Args:
        rr: An ``RRSeries`` instance.
        fmax: Highest frequency of the grid (Hz). Defaults to 0.5 Hz.

    Returns:
        Tuple ``(freqs, psd)``: frequency axis (Hz) and PSD (ms²/Hz).

    """
    t = rr.beat_times()
    x = np.asarray(rr.intervals, dtype=float)
    duration = float(t[-1] - t[0])
    if len(x) < 3 or duration <= 0:
        return np.array([0.0, fmax]), np.zeros(2)
    # Linear detrending, as for Welch, so that VLF powers stay comparable
    x = x - np.polyval(np.polyfit(t, x, 1), t)
    df = 1.0 / (4.0 * duration)
    freqs = np.arange(df, fmax + df / 2, df)
    power = lombscargle(t, x, 2.0 * np.pi * freqs)  # unnormalised
    psd = 2.0 * duration * power / len(x)
    return freqs, psd


def _ar_psd(
    signal: np.ndarray,
    fs: float,
    order: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Estimate one-sided PSD using the Yule-Walker autoregressive method.

    Solves the Yule-Walker equations (Levinson-Durbin, via scipy's
    ``solve_toeplitz``) to fit an AR(p) model of the given order, then
    evaluates the one-sided power spectral density on a frequency grid of ``_AR_NFFT`` points (≈ 0.001 Hz resolution at 4 Hz), after linear
    detrending.

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
    from scipy.signal import detrend

    n = len(signal)
    x = detrend(signal, type="linear")

    # Biased autocorrelation: R[k] = (1/N) Σ x[i] x[i+k]
    corr_full = np.correlate(x, x, mode="full")
    r = corr_full[n - 1 :] / n  # lags 0, 1, 2, ...

    # Fine grid (≈ 0.001 Hz at 4 Hz): narrow AR peaks must not fall between bins
    freqs = np.fft.rfftfreq(_AR_NFFT, d=1.0 / fs)
    if r[0] <= 1e-9:  # flat signal once detrended: no variability, no spectrum
        return freqs, np.zeros_like(freqs)

    safe_order = min(order, n // 2 - 1)

    r_col = r[:safe_order]  # first column of symmetric Toeplitz matrix
    r_rhs = r[1 : safe_order + 1]  # right-hand side: [R(1), …, R(p)]

    a_coeffs = solve_toeplitz(r_col, r_rhs)

    # Residual noise variance (prediction error power)
    sigma2 = max(r[0] - float(np.dot(a_coeffs, r_rhs)), 0.0)

    # One-sided PSD: P(f) = σ² / (fs · |A(f)|²)
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
