"""cardiolab — HRV analysis toolkit.

Scientific core of the cardioanalysis platform. Provides RR signal processing,
HRV feature extraction, physiological protocols, and analytics.

Quick-start::

    from cardiolab import RRSeries, resting_hrv, orthostatic_hrv

Submodules
----------
cardiolab.features
    Time-domain, frequency-domain and non-linear HRV metrics.
cardiolab.protocols
    Resting, orthostatic, cardiac coherence, HRR, cardiac drift and VO2max
    protocols — each returns a typed result dataclass.
cardiolab.analytics
    Baseline rolling window, readiness scoring, anomaly detection, trends.
cardiolab.visualization
    Matplotlib figures: RR signal plots, spectral (PSD, LF/HF, radar,
    heatmap) and resting evolution charts.  Import separately to avoid
    loading matplotlib when only the computational pipeline is needed::

        from cardiolab.visualization import plot_psd_welch, plot_hrv_radar

"""

from __future__ import annotations

__version__ = "0.2.0"
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
