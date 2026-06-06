"""RMSSD anomaly detection relative to a personal baseline."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures


def detect_rmssd_anomaly(
    current: HRVFeatures,
    baseline: Baseline,
    method: str = "zscore",
) -> dict:
    """Detect whether the current RMSSD deviates abnormally from the baseline.

    Three detection strategies are available:

    * ``"simple"``: percentage deviation from the rolling-window mean.
    * ``"zscore"``: standardised distance from the rolling-window mean,
      expressed in standard deviations.
    * ``"rolling"``: percentage deviation from the most recent rolling median.

    Args:
        current: HRV features of the session to evaluate.
        baseline: Personal reference containing recent session history.
        method: Detection strategy to apply. One of ``"simple"``,
            ``"zscore"``, or ``"rolling"``. Defaults to ``"zscore"``.

    Returns:
        Dictionary whose content depends on the chosen method (see
        ``_simple``, ``_zscore``, and ``_rolling`` for details). Always
        contains a ``"status"`` key.

    Raises:
        ValueError: If ``method`` is not one of the three accepted values.

    """
    if method == "simple":
        return _simple(current, baseline)
    elif method == "zscore":
        return _zscore(current, baseline)
    elif method == "rolling":
        return _rolling(current, baseline)
    else:
        raise ValueError(
            f"Unknown method: {method!r}. Choose 'simple', 'zscore', or 'rolling'."
        )


def _simple(current: HRVFeatures, baseline: Baseline) -> dict:
    """Detect RMSSD anomaly using a simple percentage deviation from the mean.

    Args:
        current: HRV features of the session to evaluate.
        baseline: Personal reference providing the rolling-window mean RMSSD.

    Returns:
        Dictionary with keys:

        * ``"method"`` — ``"simple"``.
        * ``"delta_pct"`` — percentage deviation from the baseline mean.
        * ``"status"`` — qualitative label from ``_interpret``.

        Returns ``{"status": "no_baseline"}`` when the baseline is empty.

    """
    base = baseline.mean_rmssd()
    if base is None:
        return {"status": "no_baseline"}

    delta = (current.rmssd - base) / base * 100

    return {"method": "simple", "delta_pct": delta, "status": _interpret(delta)}


def _zscore(current: HRVFeatures, baseline: Baseline) -> dict:
    """Detect RMSSD anomaly using a z-score relative to the rolling window.

    Args:
        current: HRV features of the session to evaluate.
        baseline: Personal reference. Requires at least 3 recent sessions
            to compute a meaningful standard deviation.

    Returns:
        Dictionary with keys:

        * ``"method"`` — ``"zscore"``.
        * ``"z"`` — z-score of the current RMSSD.
        * ``"status"`` — ``"low"`` (z < -2), ``"high"`` (z > 2), or
          ``"normal"``.

        Returns ``{"status": "insufficient_data"}`` when fewer than 3
        sessions are available, or ``{"status": "no_variability"}`` when
        the standard deviation is zero.

    """
    values = [r.rmssd for r in baseline.history[-baseline.window :]]
    if len(values) < 3:
        return {"status": "insufficient_data"}

    mean = np.mean(values)
    std = np.std(values)

    if std == 0:
        return {"status": "no_variability"}

    z = (current.rmssd - mean) / std

    return {
        "method": "zscore",
        "z": float(z),
        "status": "low" if z < -2 else "high" if z > 2 else "normal",
    }


def _rolling(current: HRVFeatures, baseline: Baseline) -> dict:
    """Detect RMSSD anomaly using a percentage deviation from the rolling median.

    The rolling median is more robust than the mean to occasional bad sessions
    and is therefore preferred for baseline comparisons in sports contexts.

    Args:
        current: HRV features of the session to evaluate.
        baseline: Personal reference. Requires at least ``baseline.window``
            sessions to compute a rolling median.

    Returns:
        Dictionary with keys:

        * ``"method"`` — ``"rolling"``.
        * ``"baseline"`` — most recent rolling median value.
        * ``"delta_pct"`` — percentage deviation from that median.
        * ``"status"`` — qualitative label from ``_interpret``.

        Returns ``{"status": "insufficient_data"}`` when the rolling median
        cannot be computed.

    """
    rolling = baseline.rolling_rmssd_median()
    if not rolling:
        return {"status": "insufficient_data"}

    base = rolling[-1]
    delta = (current.rmssd - base) / base * 100

    return {
        "method": "rolling",
        "baseline": base,
        "delta_pct": delta,
        "status": _interpret(delta),
    }


def _interpret(delta: float) -> str:
    """Translate a percentage RMSSD deviation into a severity label.

    Args:
        delta: Percentage deviation from the baseline reference.
            Positive values indicate RMSSD above baseline; negative below.

    Returns:
        One of ``"low_severe"`` (< -20 %), ``"low"`` (< -10 %),
        ``"high_severe"`` (> 20 %), ``"high"`` (> 10 %), or ``"normal"``.

    """
    if delta < -20:
        return "low_severe"
    elif delta < -10:
        return "low"
    elif delta > 20:
        return "high_severe"
    elif delta > 10:
        return "high"
    return "normal"
