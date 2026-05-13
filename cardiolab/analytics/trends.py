"""Long-term trend analysis of HRV metrics across a session history."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline


def trend_rmssd(baseline: Baseline) -> dict:
    """Detect the long-term trend in RMSSD across the full session history.

    Fits a first-degree polynomial (linear regression) to the RMSSD values
    ordered chronologically. The slope of the regression line indicates
    whether the user's HRV is improving, declining, or stable over time.

    Requires at least 5 sessions to produce a meaningful estimate; returns
    an ``"insufficient_data"`` status otherwise.

    Args:
        baseline: A ``Baseline`` object whose ``history`` contains
            ``HRVFeatures`` records ordered chronologically.

    Returns:
        Dictionary with the following keys:

        * ``"slope"`` (float): linear regression slope in ms per session.
          Positive values indicate improvement; negative values indicate decline.
        * ``"trend"`` (str): qualitative label — ``"increasing"``,
          ``"decreasing"``, or ``"stable"`` — based on slope magnitude
          (threshold: ±1 ms/session).

        When fewer than 5 sessions are available, returns
        ``{"status": "insufficient_data"}`` instead.

    """
    values = [r.rmssd for r in baseline.history]

    if len(values) < 5:
        return {"status": "insufficient_data"}

    x = np.arange(len(values))
    y = np.array(values)

    slope = np.polyfit(x, y, 1)[0]

    return {
        "slope": float(slope),
        "trend": _interpret_trend(slope),
    }


def _interpret_trend(slope: float) -> str:
    """Map a regression slope to a qualitative trend label.

    Args:
        slope: Linear regression slope in ms per session.

    Returns:
        ``"increasing"`` if slope > 1, ``"decreasing"`` if slope < -1,
        ``"stable"`` otherwise.

    """
    if slope > 1:
        return "increasing"
    elif slope < -1:
        return "decreasing"
    return "stable"
