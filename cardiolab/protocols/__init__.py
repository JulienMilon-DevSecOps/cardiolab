"""Physiological protocols — resting, orthostatic, and advanced cardiac tests."""

from cardiolab.protocols.cardiac_coherence import CoherenceResult, cardiac_coherence
from cardiolab.protocols.cardiac_drift import DriftResult, cardiac_drift
from cardiolab.protocols.hrr import HRRResult, heart_rate_recovery
from cardiolab.protocols.orthostatic import (
    OrthostaticPhases,
    OrthostaticResult,
    PhaseSegment,
    TransitionSegment,
    detect_phases,
    orthostatic_hrv,
)
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.protocols.vo2max import VO2maxResult, vo2max_from_hrv

__all__ = [
    # Resting
    "HRVFeatures",
    "resting_hrv",
    # Orthostatic
    "OrthostaticResult",
    "OrthostaticPhases",
    "PhaseSegment",
    "TransitionSegment",
    "orthostatic_hrv",
    "detect_phases",
    # Cardiac coherence
    "CoherenceResult",
    "cardiac_coherence",
    # Heart Rate Recovery
    "HRRResult",
    "heart_rate_recovery",
    # Cardiac drift
    "DriftResult",
    "cardiac_drift",
    # VO2max estimation
    "VO2maxResult",
    "vo2max_from_hrv",
]
