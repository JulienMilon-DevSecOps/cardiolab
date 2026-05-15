"""Resting HRV protocol: data model and feature extraction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.features.frequency_domain import frequency_domain
from cardiolab.features.time_domain import ln_rmssd, pnn50, rmssd, sdnn
from cardiolab.signals.rr import RRSeries


@dataclass
class HRVFeatures:
    """Snapshot of HRV metrics computed for a single recording session.

    This dataclass is the central output of the resting protocol. It holds all
    time-domain and frequency-domain indicators alongside session metadata, and
    is designed to be persisted in a database and later used to reconstruct a
    ``Baseline`` without reprocessing raw signals.

    Attributes:
        date: ISO-format date string identifying the recording session.
            Optional, but required for chronological ordering in a baseline.
        rmssd: Root Mean Square of Successive Differences (ms).
        ln_rmssd: Natural logarithm of RMSSD.
        sdnn: Standard Deviation of NN intervals (ms).
        pnn50: Percentage of successive pairs differing by more than 50 ms.
        mean_hr: Mean heart rate (bpm).
        vlf: Very-low-frequency band power (ms²).
        lf: Low-frequency band power (ms²).
        hf: High-frequency band power (ms²).
        lf_hf: LF/HF ratio, a marker of autonomic balance.
        hf_pct: HF power as a fraction of total power.
        lf_nu: LF power in normalised units.
        hf_nu: HF power in normalised units.
        duration: Effective recording duration in seconds.
        score: Optional readiness score (0–1). Defaults to 0.0 when not
            computed.

    """

    date: str | None = None

    rmssd: float = 0.0
    ln_rmssd: float = 0.0
    sdnn: float = 0.0
    pnn50: float = 0.0
    mean_hr: float = 0.0

    vlf: float = 0.0
    lf: float = 0.0
    hf: float = 0.0

    lf_hf: float = 0.0
    hf_pct: float = 0.0
    lf_nu: float = 0.0
    hf_nu: float = 0.0

    duration: float = 0.0
    score: float = 0.0


# ======================
# MAIN PROTOCOL
# ======================


def resting_hrv(
    rr: RRSeries,
    min_duration: float = 300.0,
    compute_score: bool = False,
) -> HRVFeatures:
    """Extract HRV features from a resting-state RR interval recording.

    Computes all standard time-domain metrics (RMSSD, ln_RMSSD, SDNN, pNN50)
    and frequency-domain metrics (VLF, LF, HF and derived ratios) from the
    provided RR series. Optionally appends a simple readiness score.

    Recommended recording conditions:
        * Duration ≥ 5 minutes for reliable frequency-domain estimates.
        * Stable supine or seated position throughout.
        * Natural, uncontrolled breathing.

    Args:
        rr: RR interval series to analyse. Should be clean (outliers removed)
            before calling this function.
        min_duration: Minimum recommended recording duration in seconds.
            A warning is silently skipped for now if the series is shorter;
            results may be less reliable below this threshold. Defaults to
            300 s (5 minutes).
        compute_score: If ``True``, computes a simple normalised readiness
            score (0–1) based on RMSSD and mean HR. Defaults to ``False``.

    Returns:
        An ``HRVFeatures`` instance populated with all computed metrics.
        ``score`` is set to ``0.0`` when ``compute_score`` is ``False``.

    """
    # ======================
    # VALIDATION
    # ======================

    duration = rr.duration

    if duration < min_duration:
        pass  # sub-threshold recordings are accepted but may yield noisy results

    # ======================
    # FEATURES
    # ======================

    rmssd_value = rmssd(rr)
    ln_rmssd_value = ln_rmssd(rr)
    sdnn_value = sdnn(rr)
    pnn50_value = pnn50(rr)
    mean_hr_value = rr.mean_hr

    frequency_indicators = frequency_domain(rr)

    # ======================
    # SCORE (simple)
    # ======================

    score = 0.0

    if compute_score:
        score = _compute_simple_score(rmssd_value, mean_hr_value)

    return HRVFeatures(
        rmssd=rmssd_value,
        ln_rmssd=ln_rmssd_value,
        sdnn=sdnn_value,
        pnn50=pnn50_value,
        mean_hr=mean_hr_value,
        vlf=frequency_indicators["VLF"],
        lf=frequency_indicators["LF"],
        hf=frequency_indicators["HF"],
        lf_hf=frequency_indicators["LF_HF"],
        hf_pct=frequency_indicators["HF_pct"],
        lf_nu=frequency_indicators["LF_nu"],
        hf_nu=frequency_indicators["HF_nu"],
        duration=duration,
        score=score,
    )


# ======================
# SIMPLE SCORE
# ======================


def _compute_simple_score(rmssd_value: float, mean_hr: float) -> float:
    """Compute a normalised readiness score from RMSSD and heart rate.

    Combines a tanh-normalised RMSSD component with an HR penalty to produce
    a score in [0, 1]. High RMSSD and low HR push the score toward 1 (good
    readiness); the reverse yields a score near 0.

    This is a simplified heuristic score. For a baseline-relative score,
    use ``readiness_score_oura`` or ``readiness_score_multi`` from
    ``cardiolab.analytics.scoring``.

    Args:
        rmssd_value: RMSSD of the current session in milliseconds.
        mean_hr: Mean heart rate of the current session in bpm.

    Returns:
        Readiness score as a float in [0, 1].

    """
    rmssd_norm = np.tanh(rmssd_value / 50.0)
    hr_penalty = np.tanh((mean_hr - 60.0) / 30.0)

    score = (rmssd_norm - hr_penalty + 1) / 2

    return float(score)
