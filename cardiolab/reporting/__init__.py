"""Tabular reporting for cardiolab protocols.

Public API::

    from cardiolab.reporting import (
        table_resting_history,
        table_resting_session,
        table_orthostatic_comparison,
        table_orthostatic_history,
    )
"""

from __future__ import annotations

from cardiolab.reporting.orthostatic import (
    table_orthostatic_comparison,
    table_orthostatic_history,
)
from cardiolab.reporting.resting import (
    table_resting_history,
    table_resting_session,
)

__all__ = [
    "table_orthostatic_comparison",
    "table_orthostatic_history",
    "table_resting_history",
    "table_resting_session",
]
