"""Tabular reporting for cardiolab protocols.

Public API::

    from cardiolab.reporting import (
        table_resting_history,
        table_resting_session,
        table_orthostatic_comparison,
        table_orthostatic_history,
        table_hrr_history,
        table_drift_history,
        table_coherence_history,
        table_vo2max_history,
        table_vo2max_session,
        table_training_load_history,
        summary_training_load,
    )
"""

from __future__ import annotations

from cardiolab.reporting.coherence import table_coherence_history
from cardiolab.reporting.drift import table_drift_history
from cardiolab.reporting.hrr import table_hrr_history
from cardiolab.reporting.orthostatic import (
    table_orthostatic_comparison,
    table_orthostatic_history,
)
from cardiolab.reporting.resting import (
    table_resting_history,
    table_resting_session,
)
from cardiolab.reporting.training_load_report import (
    summary_training_load,
    table_training_load_history,
)
from cardiolab.reporting.vo2max import (
    table_vo2max_history,
    table_vo2max_session,
)

__all__ = [
    "table_coherence_history",
    "table_drift_history",
    "table_hrr_history",
    "table_orthostatic_comparison",
    "table_orthostatic_history",
    "table_resting_history",
    "table_resting_session",
    "table_training_load_history",
    "summary_training_load",
    "table_vo2max_history",
    "table_vo2max_session",
]
