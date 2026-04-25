from __future__ import annotations

import numpy as np
from scipy.signal import welch


def frequency_domain(rr, fs=4.0):
    """
    FR :
    Analyse fréquentielle HRV via méthode de Welch.

    | Indicateur | Signification           |
    | ---------- | ----------------------- |
    | HF         | parasympathique         |
    | LF         | mix (sympa + parasympa) |
    | LF/HF      | balance autonome        |
    | HF ↑       | récupération            |
    | LF/HF ↑    | stress                  |


    EN :
    Frequency-domain HRV analysis using Welch method.
    """

    rr_intervals = np.array(rr.intervals) / 1000.0  # sec

    # ======================
    # interpolation
    # ======================

    time = np.cumsum(rr_intervals)
    time = time - time[0]

    interp_time = np.arange(0, time[-1], 1 / fs)
    interp_rr = np.interp(interp_time, time, rr_intervals)

    # ======================
    # PSD
    # ======================

    freqs, psd = welch(interp_rr, fs=fs, nperseg=min(256, len(interp_rr)))

    # ======================
    # bandes
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


def _band_power(freqs, psd, low, high):
    mask = (freqs >= low) & (freqs < high)
    return float(np.trapz(psd[mask], freqs[mask]))