"""Resting HRV protocol: data model and feature extraction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.features.frequency_domain import frequency_domain
from cardiolab.features.nonlinear import apen as _apen
from cardiolab.features.nonlinear import dfa_alpha1 as _dfa_alpha1
from cardiolab.features.nonlinear import sampen as _sampen
from cardiolab.features.nonlinear import sd1 as _sd1
from cardiolab.features.nonlinear import sd2 as _sd2
from cardiolab.features.nonlinear import sd_ratio as _sd_ratio
from cardiolab.features.time_domain import ln_rmssd, pnn50, rmssd, sdnn
from cardiolab.signals.rr import RRSeries


@dataclass
class HRVFeatures:
    """Snapshot of HRV metrics computed for a single recording session.

    This dataclass is the central output of the resting protocol. It holds all
    time-domain, frequency-domain, and non-linear indicators alongside session
    metadata, and is designed to be persisted in a database and later used to
    reconstruct a ``Baseline`` without reprocessing raw signals.

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
        hf_hr: HF power divided by mean heart rate (ms² / bpm).
            Normalises HF for heart-rate dependency.
        sd1: Poincaré SD1 — short-term beat-to-beat variability (ms).
            Equivalent to RMSSD / √2.
        sd2: Poincaré SD2 — long-term variability (ms).
            Reflects overall autonomic regulation.
        sd_ratio: SD1/SD2 ratio — shape of the Poincaré ellipse
            (dimensionless). Normal resting range ≈ 0.25–0.55.
        dfa_alpha1: DFA short-term scaling exponent (α1, scales 4–16 beats).
            Normal resting range ≈ 0.75–1.25. Returns ``nan`` for very short
            recordings.
        apen: Approximate Entropy (dimensionless). Quantifies signal
            regularity/complexity. Returns ``nan`` for short or constant
            series. Standard parameters: m=2, r=0.2·std(RR).
        sampen: Sample Entropy (dimensionless). Improved version of ApEn,
            less sensitive to recording length. Returns ``nan`` for short or
            constant series. Standard parameters: m=2, r=0.2·std(RR).
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
    hf_hr: float = 0.0

    sd1: float = 0.0
    sd2: float = 0.0
    sd_ratio: float = 0.0
    dfa_alpha1: float = 0.0

    apen: float = 0.0
    sampen: float = 0.0

    duration: float = 0.0
    score: float = 0.0

    def to_dataframe(self):
        """Return a one-row pandas DataFrame of all HRV features.

        Each field of the dataclass becomes one column. Useful for building
        time-series analyses and exporting to tabular tools.

        Returns:
            A ``pandas.DataFrame`` with one row and one column per field.

        Raises:
            ImportError: If ``pandas`` is not installed. Install with
                ``pip install cardiolab[analysis]``.

        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install cardiolab[analysis]"
            ) from exc

        return pd.DataFrame([self.to_dict()])

    def to_dict(self) -> dict:
        """Return a plain-Python dict of all HRV features.

        Returns:
            Dictionary with one key per field. ``date`` may be ``None``.
            All numeric values are native Python ``float``.

        """
        return {
            "date": self.date,
            "rmssd": self.rmssd,
            "ln_rmssd": self.ln_rmssd,
            "sdnn": self.sdnn,
            "pnn50": self.pnn50,
            "mean_hr": self.mean_hr,
            "vlf": self.vlf,
            "lf": self.lf,
            "hf": self.hf,
            "lf_hf": self.lf_hf,
            "hf_pct": self.hf_pct,
            "lf_nu": self.lf_nu,
            "hf_nu": self.hf_nu,
            "hf_hr": self.hf_hr,
            "sd1": self.sd1,
            "sd2": self.sd2,
            "sd_ratio": self.sd_ratio,
            "dfa_alpha1": self.dfa_alpha1,
            "apen": self.apen,
            "sampen": self.sampen,
            "duration": self.duration,
            "score": self.score,
        }


# ======================
# MAIN PROTOCOL
# ======================


def resting_hrv(
    rr: RRSeries,
    min_duration: float = 300.0,
    compute_score: bool = False,
    auto_clean: bool = False,
    method: str = "welch",
) -> HRVFeatures:
    """Extract HRV features from a resting-state RR interval recording.

    Computes all standard time-domain metrics (RMSSD, ln_RMSSD, SDNN, pNN50),
    frequency-domain metrics (VLF, LF, HF and derived ratios via the chosen
    spectral method), and non-linear metrics (SD1/SD2, DFA α1, ApEn, SampEn)
    from the provided RR series. Optionally appends a simple readiness score.

    Recommended recording conditions:
        * Duration ≥ 5 minutes for reliable frequency-domain estimates.
        * Stable supine or seated position throughout.
        * Natural, uncontrolled breathing.

    Args:
        rr: RR interval series to analyse.
        min_duration: Minimum recommended recording duration in seconds.
            Results may be less reliable below this threshold. Defaults to
            300 s (5 minutes).
        compute_score: If ``True``, computes a simple normalised readiness
            score (0–1) based on RMSSD and mean HR. Defaults to ``False``.
        auto_clean: If ``True``, removes physiological outliers (< 300 ms or
            > 2000 ms) from ``rr`` before computing features using the default
            ``threshold`` method. Defaults to ``False``.
        method: Spectral estimation method for frequency-domain features.
            ``"welch"`` (default) is optimal for long recordings (≥ 5 min).
            ``"ar"`` uses the autoregressive Yule-Walker method, which gives
            better spectral resolution on short segments (< 2 min) and is
            recommended for the orthostatic transition phase.

    Returns:
        An ``HRVFeatures`` instance populated with all computed metrics.
        ``score`` is set to ``0.0`` when ``compute_score`` is ``False``.

    """
    if auto_clean:
        rr = rr.remove_outliers()

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

    frequency_indicators = frequency_domain(rr, method=method)

    hf_value = frequency_indicators["HF"]
    hf_hr_value = hf_value / mean_hr_value if mean_hr_value > 0 else 0.0

    sd1_value = _sd1(rr)
    sd2_value = _sd2(rr)
    sd_ratio_value = _sd_ratio(rr)
    dfa_alpha1_value = _dfa_alpha1(rr)
    apen_value = _apen(rr)
    sampen_value = _sampen(rr)

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
        hf=hf_value,
        lf_hf=frequency_indicators["LF_HF"],
        hf_pct=frequency_indicators["HF_pct"],
        lf_nu=frequency_indicators["LF_nu"],
        hf_nu=frequency_indicators["HF_nu"],
        hf_hr=hf_hr_value,
        sd1=sd1_value,
        sd2=sd2_value,
        sd_ratio=sd_ratio_value,
        dfa_alpha1=dfa_alpha1_value,
        apen=apen_value,
        sampen=sampen_value,
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
