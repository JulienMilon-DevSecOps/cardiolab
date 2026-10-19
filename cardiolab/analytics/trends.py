"""Statistically qualified trend analysis of HRV metrics and scores.

A trend is only reported when it is both **significant** and **large enough**:

* the slope of a least-squares line (``scipy.stats.linregress``) over a window
  of calendar days, with its r² and p-value;
* the fitted change over the window, in % of the window mean — a relative
  threshold, comparable between athletes whatever their RMSSD level (an
  absolute ms threshold means a lot for an RMSSD of 25 ms and little for
  120 ms).

Label: ``increasing`` / ``decreasing`` when p < ``alpha`` and the change
exceeds ``min_change_pct``; ``stable`` otherwise; ``insufficient_data`` with
fewer than ``min_points`` values.

Successive HRV values are not independent (a low day is often followed by
another low day): with positively autocorrelated residuals, the ordinary
least-squares p-value is too optimistic. The p-value therefore uses the
**effective sample size** ``n_eff = n × (1 − r1) / (1 + r1)``, ``r1`` being
the lag-1 autocorrelation of the residuals (Santer et al. 2000).

References:
    Santer, B. D., Wigley, T. M. L., Boyle, J. S., Gaffen, D. J., Hnilo,
    J. J., Nychka, D., Parker, D. E., & Taylor, K. E. (2000). Statistical
    significance of trends and trend differences in layer-average
    atmospheric temperature time series. *Journal of Geophysical Research*,
    105(D6), 7337–7356.

Day-to-day HRV is noisy: no predictive model (ARIMA, HMM…) is attempted.

"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from scipy.stats import linregress
from scipy.stats import t as student_t

from cardiolab.analytics.baseline import Baseline

MIN_POINTS = 5
"""Minimum values for a trend."""

ALPHA = 0.05
"""Significance level of the slope."""

MIN_CHANGE_PCT = 5.0
"""Minimum fitted change over the window (% of the window mean)."""

LABELS: tuple[str, ...] = ("increasing", "decreasing", "stable", "insufficient_data")
"""Trend labels."""


@dataclass(frozen=True)
class TrendResult:
    """Linear trend of a series over a window.

    Attributes:
        slope: Slope per day (per session when the series has no dates), in
            the unit of the series.
        intercept: Fitted value at the first point of the window.
        r2: Coefficient of determination.
        p_value: Two-sided p-value of the slope (H0: slope = 0), corrected
            for the autocorrelation of the residuals.
        n: Number of values used.
        span_days: Days between the first and last value (sessions − 1
            without dates).
        mean: Mean of the values.
        change_pct: Fitted change over the window, in % of ``mean``.
        label: ``increasing``, ``decreasing``, ``stable`` or
            ``insufficient_data``.
        n_eff: Effective sample size used for the p-value (``n`` when the
            residuals are not positively autocorrelated).

    """

    slope: float
    intercept: float
    r2: float
    p_value: float
    n: int
    span_days: float
    mean: float
    change_pct: float
    label: str
    n_eff: float = math.nan

    @property
    def significant(self) -> bool:
        """``True`` when the slope differs from zero at the 5 % level."""
        return math.isfinite(self.p_value) and self.p_value < ALPHA


_INSUFFICIENT = dict(
    slope=math.nan,
    intercept=math.nan,
    r2=math.nan,
    p_value=math.nan,
    span_days=0.0,
    mean=math.nan,
    change_pct=math.nan,
    label="insufficient_data",
)


def _effective_n(residuals: np.ndarray) -> float:
    """Return ``n × (1 − r1) / (1 + r1)`` — ``n`` when ``r1 ≤ 0`` (Santer et al. 2000)."""
    n = len(residuals)
    denom = float(np.sum(residuals**2))
    r1 = float(np.sum(residuals[:-1] * residuals[1:]) / denom) if denom > 0 else 0.0
    return n * (1.0 - r1) / (1.0 + r1) if r1 > 0 else float(n)


def _slope_p_value(fit, x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Two-sided p-value of the slope with the effective sample size, and ``n_eff``."""
    n = len(y)
    n_eff = _effective_n(y - (fit.intercept + fit.slope * x))
    if n_eff >= n:
        return float(fit.pvalue), float(n)
    if n_eff <= 2.0:
        return 1.0, n_eff  # nearly all values redundant: no evidence of a trend
    se = fit.stderr * math.sqrt((n - 2) / (n_eff - 2))
    p = 2.0 * float(student_t.sf(abs(fit.slope) / se, n_eff - 2)) if se > 0 else 0.0
    return p, n_eff


def _to_day(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _xy(series) -> tuple[np.ndarray, np.ndarray, list[date] | None]:
    """X (days or session index), Y and days of a series (``nan`` dropped)."""
    items = list(series)
    if items and isinstance(items[0], (tuple, list)):
        pairs = sorted(
            (
                (_to_day(d), float(v))
                for d, v in items
                if v is not None and math.isfinite(v)
            ),
            key=lambda p: p[0],
        )
        if not pairs:
            return np.array([]), np.array([]), []
        days = [d for d, _ in pairs]
        x = np.array([(d - days[0]).days for d in days], dtype=float)
        return x, np.array([v for _, v in pairs]), days
    y = np.array([float(v) for v in items if v is not None and math.isfinite(v)])
    return np.arange(len(y), dtype=float), y, None


def linear_trend(
    series: Sequence,
    window_days: int | None = None,
    *,
    end: str | date | None = None,
    min_points: int = MIN_POINTS,
    alpha: float = ALPHA,
    min_change_pct: float = MIN_CHANGE_PCT,
) -> TrendResult:
    """Fit a linear trend and qualify it (slope, r², p-value, relative change).

    Changed in 0.5.0: the p-value accounts for the autocorrelation of the
    residuals (effective sample size, Santer et al. 2000).

    Args:
        series: ``[(date, value), …]`` (ISO strings or ``date``) — the x axis
            is in calendar days, so gaps are respected — or plain values (x =
            session index). ``None`` / ``nan`` values are dropped.
        window_days: Only use the days ``(end − window_days, end]``. ``None``
            → the whole series. Ignored for a series without dates.
        end: Last day of the window. Defaults to the last date of the series.
        min_points: Minimum values, otherwise ``insufficient_data``.
        alpha: Significance level of the slope.
        min_change_pct: Minimum fitted change over the window (% of the mean)
            for ``increasing`` / ``decreasing``.

    Returns:
        A :class:`TrendResult`.

    """
    x, y, days = _xy(series)
    if days and window_days is not None:
        last = _to_day(end) if end is not None else days[-1]
        first = last - timedelta(days=window_days)
        keep = np.array([first < d <= last for d in days])
        x, y = x[keep], y[keep]
        if len(x):
            x = x - x[0]
    n = len(y)
    if n < min_points or np.ptp(x) == 0:
        return TrendResult(n=n, **_INSUFFICIENT)

    mean = float(np.mean(y))
    if np.ptp(y) == 0:  # perfectly flat: no trend, linregress is undefined
        slope, intercept, r2, p, n_eff = 0.0, mean, 0.0, 1.0, float(n)
    else:
        fit = linregress(x, y)
        slope, intercept = float(fit.slope), float(fit.intercept)
        r2 = float(fit.rvalue**2)
        p, n_eff = _slope_p_value(fit, x, y)
    span = float(x[-1] - x[0])
    change_pct = 100.0 * slope * span / abs(mean) if mean else math.nan

    if p < alpha and math.isfinite(change_pct) and abs(change_pct) >= min_change_pct:
        label = "increasing" if slope > 0 else "decreasing"
    else:
        label = "stable"
    return TrendResult(
        slope=slope,
        intercept=intercept,
        r2=r2,
        p_value=p,
        n=n,
        span_days=span,
        mean=mean,
        change_pct=change_pct,
        label=label,
        n_eff=n_eff,
    )


# ======================
# SUSTAINED DECLINE
# ======================


@dataclass(frozen=True)
class SustainedDecline:
    """Outcome of :func:`detect_sustained_decline`.

    Attributes:
        detected: ``True`` when the last ``run_length`` values (at least
            ``min_sessions``) are all below the threshold.
        run_length: Number of consecutive values, ending with the last one,
            below ``reference_mean + threshold × reference_sd``.
        reference_mean: Mean of the reference values.
        reference_sd: Standard deviation of the reference values.
        limit: ``reference_mean + threshold × reference_sd``.

    """

    detected: bool
    run_length: int
    reference_mean: float
    reference_sd: float
    limit: float


def detect_sustained_decline(
    scores: Sequence,
    min_sessions: int = 5,
    threshold: float = -0.5,
    reference_size: int = 30,
) -> SustainedDecline:
    """Detect a run of consecutive values below the athlete's usual range.

    The reference is made of the values preceding the last ``min_sessions``
    ones (at most ``reference_size``). A decline is **sustained** when the
    last ``min_sessions`` values are all below ``mean + threshold × SD`` of
    that reference — with the default ``threshold = −0.5``, below the usual
    range by more than half a standard deviation, the smallest worthwhile
    change used in HRV monitoring.

    Args:
        scores: Values in chronological order — plain numbers or
            ``[(date, value), …]``.
        min_sessions: Consecutive values required.
        threshold: Limit in reference SD units (negative = below the mean).
        reference_size: Maximum number of reference values.

    Returns:
        A :class:`SustainedDecline` (``detected=False`` with fewer than
        ``2 × min_sessions`` values).

    """
    _, y, _ = _xy(scores)
    if len(y) < 2 * min_sessions:
        return SustainedDecline(False, 0, math.nan, math.nan, math.nan)
    reference = y[:-min_sessions][-reference_size:]
    mean, sd = float(np.mean(reference)), float(np.std(reference, ddof=1))
    limit = mean + threshold * sd
    run = 0
    for value in y[::-1]:
        if value >= limit:
            break
        run += 1
    return SustainedDecline(
        detected=run >= min_sessions,
        run_length=run,
        reference_mean=mean,
        reference_sd=sd,
        limit=limit,
    )


# ======================
# REPORT
# ======================


def _metric_series(history, metric: str) -> list[tuple[str, float]]:
    sessions = history.sessions if hasattr(history, "sessions") else history
    return [
        (s.date, float(getattr(s, metric)))
        for s in sessions
        if s.date and getattr(s, metric, None) is not None
    ]


def trend_report(history, metric: str = "score"):
    """Build a rolling trend report — one row per session.

    Args:
        history: :class:`~cardiolab.analytics.baseline.Baseline` (``poor``
            sessions excluded) or list of dated ``HRVFeatures``.
        metric: Attribute analysed (``"score"``, ``"rmssd"``, ``"ln_rmssd"``…).

    Returns:
        A ``pandas.DataFrame`` with columns ``date``, ``<metric>``,
        ``slope_7d`` and ``slope_30d`` (per day, ``nan`` with fewer than 5
        values in the window), ``change_30d_pct``, ``p_30d`` and
        ``trend_label`` (30-day label).

    Raises:
        ImportError: If ``pandas`` is not installed
            (``pip install cardiolab[analysis]``).

    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required for trend_report(). "
            "Install it with: pip install cardiolab[analysis]"
        ) from exc

    series = sorted(_metric_series(history, metric), key=lambda p: str(p[0])[:10])
    rows = []
    for day, value in series:
        week = linear_trend(series, 7, end=day)
        month = linear_trend(series, 30, end=day)
        rows.append(
            {
                "date": str(day)[:10],
                metric: value,
                "slope_7d": week.slope,
                "slope_30d": month.slope,
                "change_30d_pct": month.change_pct,
                "p_30d": month.p_value,
                "trend_label": month.label,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "date",
            metric,
            "slope_7d",
            "slope_30d",
            "change_30d_pct",
            "p_30d",
            "trend_label",
        ],
    )


# ======================
# BACKWARD COMPATIBILITY
# ======================


def trend_rmssd(baseline: Baseline) -> dict:
    """Long-term RMSSD trend over the whole history (kept for compatibility).

    Wrapper around :func:`linear_trend` on the RMSSD of the usable sessions
    (``poor`` excluded), with the session index as x — as before. For a trend
    in calendar days or over a window, call :func:`linear_trend` directly.

    Changed in 0.5.0: the label is ``increasing`` / ``decreasing`` only when
    the slope is significant (p < 0.05) **and** the fitted change reaches 5 %
    of the mean RMSSD — it used a fixed ±1 ms/session threshold without any
    significance test.

    Args:
        baseline: A ``Baseline``.

    Returns:
        ``{"slope", "trend", "p_value", "r2", "change_pct"}`` — ``slope`` in
        ms per session (as before); or ``{"status": "insufficient_data"}``
        with fewer than 5 sessions.

    """
    sessions = baseline.sessions
    if len(sessions) < MIN_POINTS:
        return {"status": "insufficient_data"}
    # Session index as x, as before (use linear_trend for calendar days)
    result = linear_trend([s.rmssd for s in sessions])
    return {
        "slope": result.slope,
        "trend": result.label if result.label != "insufficient_data" else "stable",
        "p_value": result.p_value,
        "r2": result.r2,
        "change_pct": result.change_pct,
    }
