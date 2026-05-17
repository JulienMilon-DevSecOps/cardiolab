"""cardiolab — HRV analysis toolkit.

Scientific core of the cardioanalysis platform. Provides RR signal processing,
HRV feature extraction, physiological protocols, and analytics.

Quick-start::

    from cardiolab import RRSeries, resting_hrv, orthostatic_hrv

"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Julien MILON"

from cardiolab.protocols.orthostatic import OrthostaticResult, orthostatic_hrv
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

__all__ = [
    "__version__",
    # Core data structures
    "RRSeries",
    "PhysiologicalWarning",
    # Resting protocol
    "HRVFeatures",
    "resting_hrv",
    # Orthostatic protocol
    "OrthostaticResult",
    "orthostatic_hrv",
]
