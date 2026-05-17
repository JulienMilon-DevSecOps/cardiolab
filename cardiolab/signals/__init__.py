"""Signal data structures — ECG and RR interval series."""

from cardiolab.signals.ecg import ECGSignal
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

__all__ = [
    "RRSeries",
    "PhysiologicalWarning",
    "ECGSignal",
]
