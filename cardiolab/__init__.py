"""cardiolab — HRV analysis toolkit.

Scientific core of the cardioanalysis platform. Provides RR signal processing,
HRV feature extraction, physiological protocols, analytics, and training load
modelling.

Quick-start::

    from cardiolab import RRSeries, resting_hrv, Baseline, TrainingLoad

Submodules
----------
cardiolab.signals
    RR series and ECG signal processing.
cardiolab.features
    Time-domain, frequency-domain and non-linear HRV metrics.
cardiolab.protocols
    Resting, orthostatic, cardiac coherence, HRR, cardiac drift and VO2max
    protocols — each returns a typed result dataclass.
cardiolab.analytics
    Baseline rolling window, readiness scoring, anomaly detection, trends,
    and training load (ATL/CTL/TSB, TRIMP).
cardiolab.visualization
    Matplotlib figures. Import separately to avoid loading matplotlib when
    only the computational pipeline is needed::

        from cardiolab.visualization import plot_psd_welch, plot_hrv_radar

cardiolab.database
    PostgreSQL persistence layer and migration runner. Import separately to
    avoid requiring psycopg2 in pure-computation contexts::

        from cardiolab.database import HRVRepository, run_migrations

"""

from __future__ import annotations

__version__ = "0.3.0"
__author__ = "Julien MILON"

# ── Signals ───────────────────────────────────────────────────────────────────
# ── Analytics — baseline and scoring ─────────────────────────────────────────
from cardiolab.analytics.anomaly import detect_rmssd_anomaly
from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import (
    coherence_score_100,
    drift_score,
    hrr_score,
    orthostatic_score,
    readiness_score_composite,
    readiness_score_multi,
    readiness_score_nonlinear,
    vo2max_score,
)

# ── Analytics — training load ─────────────────────────────────────────────────
from cardiolab.analytics.training_load import (
    TrainingLoad,
    compute_atl,
    compute_ctl,
    compute_tsb,
    load_readiness_for_date,
    trimp_banister,
    trimp_hrv_based,
)
from cardiolab.analytics.trends import trend_rmssd

# ── Protocols — functions and result types ────────────────────────────────────
from cardiolab.protocols.cardiac_coherence import CoherenceResult, cardiac_coherence
from cardiolab.protocols.cardiac_drift import DriftResult, cardiac_drift
from cardiolab.protocols.hrr import HRRResult, heart_rate_recovery
from cardiolab.protocols.orthostatic import OrthostaticResult, orthostatic_hrv
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.protocols.vo2max import VO2maxResult, vo2max_from_hrv
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

__all__ = [
    "__version__",
    # ── Signals
    "RRSeries",
    "PhysiologicalWarning",
    # ── Protocols — functions
    "resting_hrv",
    "orthostatic_hrv",
    "cardiac_coherence",
    "heart_rate_recovery",
    "cardiac_drift",
    "vo2max_from_hrv",
    # ── Protocols — result types
    "HRVFeatures",
    "OrthostaticResult",
    "CoherenceResult",
    "HRRResult",
    "DriftResult",
    "VO2maxResult",
    # ── Analytics — baseline
    "Baseline",
    # ── Analytics — readiness scoring (baseline-relative)
    "readiness_score_multi",
    "readiness_score_nonlinear",
    "readiness_score_composite",
    # ── Analytics — protocol scores (absolute thresholds)
    "hrr_score",
    "coherence_score_100",
    "drift_score",
    "vo2max_score",
    "orthostatic_score",
    # ── Analytics — anomaly and trends
    "detect_rmssd_anomaly",
    "trend_rmssd",
    # ── Training load
    "TrainingLoad",
    "compute_atl",
    "compute_ctl",
    "compute_tsb",
    "trimp_hrv_based",
    "trimp_banister",
    "load_readiness_for_date",
]
