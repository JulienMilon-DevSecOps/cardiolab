"""Signal data structures — ECG and RR interval series."""

from cardiolab.signals.artifacts import ArtifactReport
from cardiolab.signals.ecg import ECGSignal
from cardiolab.signals.quality import SignalQuality, signal_quality
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

__all__ = [
    "RRSeries",
    "PhysiologicalWarning",
    "ECGSignal",
    "ArtifactReport",
    "SignalQuality",
    "signal_quality",
]
