"""Training adaptation monitoring from daily lnRMSSD (Plews, Buchheit).

A single morning RMSSD is noisy from one day to the next. The reference
approach for monitoring training adaptation looks at the **7-day rolling mean
of lnRMSSD**, its **coefficient of variation** (CV) and the **smallest
worthwhile change** (SWC) of the athlete (Plews et al. 2012, 2013; Buchheit
2014):

* the 7-day mean inside the SWC band around the athlete's baseline → normal
  day-to-day fluctuation;
* above the band → the athlete copes well with training;
* below the band → maladaptation; with an elevated CV (unstable values) →
  risk of non-functional overreaching.

Definitions used here:

* **Daily value** — lnRMSSD of each measurement day (mean when a day has
  several sessions). ``poor``-quality sessions are left out (see
  :attr:`Baseline.sessions <cardiolab.analytics.baseline.Baseline.sessions>`).
* **7-day mean / CV** — over the calendar days ``(d − 7, d]``; at least 3
  measurements (Plews et al. 2014), otherwise ``nan``. CV = SD / mean × 100 of the daily lnRMSSD.
* **SWC band** — baseline = daily lnRMSSD over the 28 days **preceding** the
  7-day window (at least 6 measurements); SWC = 0.5 × SD; band = baseline
  mean ± SWC. The evaluated week is not part of its own reference.
* **Elevated CV** — 7-day CV above the mean + 1 SD of the 7-day CVs of the
  same baseline days (cardiolab's operational threshold).

References:
    Plews, D. J., Laursen, P. B., Kilding, A. E., & Buchheit, M. (2012).
    Heart rate variability in elite triathletes, is variation in variability
    the key to effective training? A case comparison. *European Journal of
    Applied Physiology*, 112(11), 3729–3741.

    Plews, D. J., Laursen, P. B., Stanley, J., Kilding, A. E., & Buchheit, M.
    (2013). Training adaptation and heart rate variability in elite endurance
    athletes: opening the door to effective monitoring. *Sports Medicine*,
    43(9), 773–781.

    Plews, D. J., Laursen, P. B., Le Meur, Y., Hausswirth, C., Kilding, A. E.,
    & Buchheit, M. (2014). Monitoring training with heart-rate variability:
    how much compliance is needed for valid assessment? *International
    Journal of Sports Physiology and Performance*, 9(5), 783–790.

    Buchheit, M. (2014). Monitoring training status with HR measures: do all
    roads lead to Rome? *Frontiers in Physiology*, 5, 73.

"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from cardiolab.protocols.resting import HRVFeatures

WINDOW_DAYS = 7
"""Length of the rolling window (calendar days)."""

MIN_MEASURES = 3
"""Minimum measurements in a 7-day window, otherwise the value is ``nan``."""

BASELINE_DAYS = 28
"""Length of the baseline used for the SWC band (calendar days)."""

MIN_BASELINE_MEASURES = 6
"""Minimum measurements in the baseline (two valid weeks)."""

MIN_SD = 0.05
"""Floor of the reference SD in :func:`baseline_relative_score` (≈ 5 % of RMSSD).

Six nearly identical previous values would otherwise turn any small change
into an extreme score."""

SWC_FACTOR = 0.5
"""SWC = ``SWC_FACTOR`` × SD of the baseline daily lnRMSSD."""

CV_SD_FACTOR = 1.0
"""Elevated CV: above the baseline mean CV + ``CV_SD_FACTOR`` × SD."""

STATES: tuple[str, ...] = ("coping", "normal", "maladaptation", "overreaching_risk")
"""Training adaptation states returned by :func:`interpret_trend_state`."""


# ======================
# DAILY SERIES
# ======================


def _sessions(baseline) -> list[HRVFeatures]:
    """Sessions of a ``Baseline`` (``poor`` excluded) or of a plain list."""
    return list(baseline.sessions) if hasattr(baseline, "sessions") else list(baseline)


def _day(value) -> date | None:
    """Calendar day of an ISO date / datetime string (``None`` if missing)."""
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _ln_rmssd(session: HRVFeatures) -> float | None:
    """Return the lnRMSSD of a session — ``log(rmssd)``, else ``ln_rmssd``."""
    if session.rmssd and session.rmssd > 0 and math.isfinite(session.rmssd):
        return math.log(session.rmssd)
    if session.ln_rmssd and math.isfinite(session.ln_rmssd):
        return float(session.ln_rmssd)
    return None


def daily_ln_rmssd(baseline) -> list[tuple[date, float]]:
    """Daily lnRMSSD, chronological — mean of the sessions of each day.

    Args:
        baseline: A :class:`~cardiolab.analytics.baseline.Baseline` (its
            :attr:`sessions`, ``poor`` excluded) or a list of
            ``HRVFeatures``. Sessions without date or RMSSD are skipped.

    Returns:
        ``[(day, ln_rmssd), …]`` sorted by day.

    """
    by_day: dict[date, list[float]] = {}
    for s in _sessions(baseline):
        day, value = _day(s.date), _ln_rmssd(s)
        if day is not None and value is not None:
            by_day.setdefault(day, []).append(value)
    return [(d, float(np.mean(v))) for d, v in sorted(by_day.items())]


def _window(daily: list[tuple[date, float]], end: date, days: int) -> list[float]:
    """Daily values in the calendar window ``(end − days, end]``."""
    start = end - timedelta(days=days)
    return [v for d, v in daily if start < d <= end]


def _mean_cv(values: list[float], min_count: int) -> tuple[float, float]:
    """Mean and CV (%) of ``values``; ``nan`` when fewer than ``min_count``."""
    if len(values) < min_count:
        return math.nan, math.nan
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return mean, 100.0 * sd / mean if mean else math.nan


# ======================
# ROLLING STATISTICS
# ======================


def rolling_ln_rmssd(
    baseline,
    window: int = WINDOW_DAYS,
    min_count: int = MIN_MEASURES,
) -> list[tuple[str, float]]:
    """7-day rolling mean of lnRMSSD, on each measurement day.

    Args:
        baseline: ``Baseline`` or list of ``HRVFeatures``.
        window: Window length in calendar days.
        min_count: Minimum measurements in the window (else ``nan``).

    Returns:
        ``[(iso_date, mean), …]``.

    """
    daily = daily_ln_rmssd(baseline)
    return [
        (d.isoformat(), _mean_cv(_window(daily, d, window), min_count)[0])
        for d, _ in daily
    ]


def rolling_cv(
    baseline,
    window: int = WINDOW_DAYS,
    min_count: int = MIN_MEASURES,
) -> list[tuple[str, float]]:
    """7-day rolling coefficient of variation of lnRMSSD (%), on each measurement day.

    Args:
        baseline: ``Baseline`` or list of ``HRVFeatures``.
        window: Window length in calendar days.
        min_count: Minimum measurements in the window (else ``nan``).

    Returns:
        ``[(iso_date, cv_percent), …]``.

    """
    daily = daily_ln_rmssd(baseline)
    return [
        (d.isoformat(), _mean_cv(_window(daily, d, window), min_count)[1])
        for d, _ in daily
    ]


@dataclass(frozen=True)
class SWCBand:
    """Smallest worthwhile change band around the baseline lnRMSSD.

    Attributes:
        mean: Baseline mean of the daily lnRMSSD.
        swc: Smallest worthwhile change (``factor`` × SD).
        low: ``mean − swc``.
        high: ``mean + swc``.
        n: Number of measurements in the baseline.

    """

    mean: float
    swc: float
    low: float
    high: float
    n: int

    def contains(self, value: float) -> bool:
        """Return ``True`` when ``value`` lies inside the band."""
        return self.low <= value <= self.high


def _swc_band(
    daily: list[tuple[date, float]],
    at: date,
    factor: float,
    baseline_days: int,
    min_count: int,
) -> SWCBand | None:
    values = _window(daily, at, baseline_days)
    if len(values) < min_count:
        return None
    mean = float(np.mean(values))
    swc = factor * float(np.std(values, ddof=1))
    return SWCBand(mean=mean, swc=swc, low=mean - swc, high=mean + swc, n=len(values))


def swc_band(
    baseline,
    factor: float = SWC_FACTOR,
    baseline_days: int = BASELINE_DAYS,
    at: str | None = None,
    min_count: int = MIN_BASELINE_MEASURES,
    window: int = WINDOW_DAYS,
) -> SWCBand | None:
    """SWC band of the athlete: baseline mean lnRMSSD ± ``factor`` × SD.

    The band judges the 7-day window ending on ``at``; its baseline is made
    of the ``baseline_days`` days **before** that window — ``(at − window −
    baseline_days, at − window]`` — so that a change in progress does not
    shift its own reference.

    Args:
        baseline: ``Baseline`` or list of ``HRVFeatures``.
        factor: SWC as a fraction of the baseline SD. Defaults to 0.5.
        baseline_days: Baseline length in calendar days. Defaults to 28.
        at: Last day of the evaluated window (ISO). Defaults to the last
            measurement day.
        min_count: Minimum measurements in the baseline.
        window: Length of the evaluated window, excluded from the baseline.
            ``0`` → baseline ending on ``at``.

    Returns:
        The :class:`SWCBand`, or ``None`` without enough measurements.

    """
    daily = daily_ln_rmssd(baseline)
    if not daily:
        return None
    end = _day(at) if at else daily[-1][0]
    return _swc_band(
        daily, end - timedelta(days=window), factor, baseline_days, min_count
    )


# ======================
# INTERPRETATION
# ======================


def interpret_trend_state(
    mean_7d: float,
    band: SWCBand | None,
    cv_7d: float | None = None,
    cv_threshold: float | None = None,
) -> str | None:
    """Training adaptation state from the 7-day lnRMSSD mean and CV.

    Simplified decision grid after Plews et al. (2012, 2013) and Buchheit
    (2014):

    | 7-day mean | 7-day CV | State |
    |------------|----------|-------|
    | above the SWC band | — | ``coping`` |
    | inside the band | — | ``normal`` |
    | below the band | not elevated | ``maladaptation`` |
    | below the band | elevated | ``overreaching_risk`` |

    Args:
        mean_7d: 7-day rolling mean of lnRMSSD.
        band: SWC band (``None`` → not enough history).
        cv_7d: 7-day CV of lnRMSSD (%).
        cv_threshold: CV above which variability is considered elevated.

    Returns:
        One of :data:`STATES`, or ``None`` when it cannot be assessed.

    """
    if band is None or mean_7d is None or not math.isfinite(mean_7d):
        return None
    if mean_7d > band.high:
        return "coping"
    if mean_7d >= band.low:
        return "normal"
    elevated = (
        cv_7d is not None
        and cv_threshold is not None
        and math.isfinite(cv_7d)
        and cv_7d > cv_threshold
    )
    return "overreaching_risk" if elevated else "maladaptation"


@dataclass(frozen=True)
class MonitoringPoint:
    """Monitoring values of one measurement day.

    Attributes:
        date: ISO date.
        ln_rmssd: Daily lnRMSSD.
        mean_7d: 7-day rolling mean (``nan`` with fewer than 3 measurements).
        cv_7d: 7-day CV in % (``nan`` likewise).
        n_7d: Measurements in the 7-day window.
        band: SWC band on that day (``None`` without enough history).
        cv_threshold: Elevated-CV threshold on that day (``None`` likewise).
        state: :func:`interpret_trend_state` (``None`` when not assessable).

    """

    date: str
    ln_rmssd: float
    mean_7d: float
    cv_7d: float
    n_7d: int
    band: SWCBand | None
    cv_threshold: float | None
    state: str | None


def monitoring_series(
    baseline,
    *,
    window: int = WINDOW_DAYS,
    min_count: int = MIN_MEASURES,
    baseline_days: int = BASELINE_DAYS,
    factor: float = SWC_FACTOR,
    cv_sd_factor: float = CV_SD_FACTOR,
) -> list[MonitoringPoint]:
    """Full monitoring series — one :class:`MonitoringPoint` per measurement day.

    Args:
        baseline: ``Baseline`` (``poor`` sessions excluded) or list of
            ``HRVFeatures``.
        window: Rolling window (days).
        min_count: Minimum measurements per rolling window.
        baseline_days: SWC baseline length (days).
        factor: SWC factor.
        cv_sd_factor: Elevated CV = mean + ``cv_sd_factor`` × SD of the
            baseline 7-day CVs.

    Returns:
        Chronological list of monitoring points.

    """
    daily = daily_ln_rmssd(baseline)
    stats = [(d, v, _window(daily, d, window)) for d, v in daily]
    means_cvs = {d: _mean_cv(w, min_count) for d, _, w in stats}

    points = []
    for d, value, w in stats:
        mean, cv = means_cvs[d]
        # Baseline = the days BEFORE the 7-day window, so that a change in
        # progress does not drag its own reference along
        base_end = d - timedelta(days=window)
        band = _swc_band(daily, base_end, factor, baseline_days, MIN_BASELINE_MEASURES)
        start = base_end - timedelta(days=baseline_days)
        past_cvs = [
            c
            for dd, (_, c) in means_cvs.items()
            if start < dd <= base_end and math.isfinite(c)
        ]
        threshold = (
            float(np.mean(past_cvs) + cv_sd_factor * np.std(past_cvs, ddof=1))
            if len(past_cvs) >= min_count
            else None
        )
        points.append(
            MonitoringPoint(
                date=d.isoformat(),
                ln_rmssd=value,
                mean_7d=mean,
                cv_7d=cv,
                n_7d=len(w),
                band=band,
                cv_threshold=threshold,
                state=interpret_trend_state(mean, band, cv, threshold),
            )
        )
    return points


def as_monitoring_points(source) -> list[MonitoringPoint]:
    """Return ``source`` as monitoring points.

    Args:
        source: Points of :func:`monitoring_series` (returned as is), a
            ``Baseline`` or a list of ``HRVFeatures`` (computed).

    Returns:
        The monitoring points.

    """
    if (
        isinstance(source, list)
        and source
        and all(isinstance(p, MonitoringPoint) for p in source)
    ):
        return source
    return monitoring_series(source)


# ======================
# READINESS COMPONENTS
# ======================


def baseline_relative_score(
    value: float,
    reference: list[float],
    *,
    higher_is_better: bool = True,
    min_count: int = MIN_BASELINE_MEASURES,
    min_sd: float = MIN_SD,
) -> float:
    """Score a value against the athlete's own reference, in [0, 100].

    ``50 ± 50 × tanh(Δ / (2 × SD))`` with ``Δ`` = value − reference mean —
    i.e. ``Δ / (4 × SWC)`` with SWC = 0.5 × SD: ±1 SWC → 62 / 38, ±1 SD →
    73 / 27, ±2 SD → 88 / 12 (Kiviniemi et al. 2007; Plews et al. 2013).

    Args:
        value: Today's value.
        reference: Previous values (the baseline).
        higher_is_better: Direction of the score.
        min_count: Minimum reference values, otherwise 50 (neutral).
        min_sd: Floor of the reference SD.

    Returns:
        Score in [0, 100]; 50 = equal to the usual level.

    """
    values = [v for v in reference if v is not None and math.isfinite(v)]
    if value is None or not math.isfinite(value) or len(values) < min_count:
        return 50.0
    sd = max(float(np.std(values, ddof=1)), min_sd)
    z = (value - float(np.mean(values))) / (2.0 * sd)
    return float(50.0 + 50.0 * math.tanh(z if higher_is_better else -z))


def _previous_days(
    baseline, today: date | None, days: int
) -> list[tuple[object, list]]:
    """Sessions of the ``days`` days before ``today`` (today excluded), by day.

    Without a date for today, the last ``days`` sessions (one group each).
    """
    if today is None:
        return [(i, [s]) for i, s in enumerate(_sessions(baseline)[-days:])]
    start = today - timedelta(days=days + 1)
    by_day: dict[date, list] = {}
    for s in _sessions(baseline):
        day = _day(s.date)
        if day is not None and start < day < today:
            by_day.setdefault(day, []).append(s)
    return sorted(by_day.items())


def ln_rmssd_day_score(
    current: HRVFeatures,
    baseline,
    *,
    baseline_days: int = BASELINE_DAYS,
) -> float:
    """LnRMSSD component of the readiness score, in [0, 100].

    Today's lnRMSSD against the daily lnRMSSD of the ``baseline_days`` days
    before today (:func:`baseline_relative_score`, higher is better): the
    individual reference band of HRV-guided training (Kiviniemi et al. 2007;
    Plews et al. 2013). Neutral (50) with fewer than 6 previous measurement
    days. Undated sessions: the last ``baseline_days`` sessions are the
    reference.

    Args:
        current: Session being scored.
        baseline: Previous sessions (``Baseline`` — ``poor`` excluded — or a
            list of ``HRVFeatures``).
        baseline_days: Reference length in calendar days. Defaults to 28.

    Returns:
        Score in [0, 100].

    """
    today, value = _day(current.date), _ln_rmssd(current)
    if value is None:
        return 50.0
    reference = [
        float(np.mean([v for s in day_sessions if (v := _ln_rmssd(s)) is not None]))
        for _, day_sessions in _previous_days(baseline, today, baseline_days)
        if any(_ln_rmssd(s) is not None for s in day_sessions)
    ]
    return baseline_relative_score(value, reference)


def dfa_alpha1_score(
    current: HRVFeatures,
    baseline,
    *,
    baseline_days: int = BASELINE_DAYS,
) -> float:
    """DFA α1 component of the readiness score, in [0, 100].

    Today's DFA α1 against the values of the ``baseline_days`` days before
    today, **lower is better**: vagal activity lowers the short-term scaling
    exponent and sympathetic activity raises it (Castiglioni et al. 2011),
    so an α1 above the usual level points to a less vagal state. Neutral (50)
    with fewer than 6 previous values or when α1 was not computed (0 / nan).
    Undated sessions: the last ``baseline_days`` sessions are the reference.

    Changed in 0.5.0: α1 was scored against the fixed 0.75 threshold — a
    threshold of exercise studies (aerobic threshold), not a resting norm —
    with "higher is better".

    Args:
        current: Session being scored.
        baseline: Previous sessions.
        baseline_days: Reference length in calendar days. Defaults to 28.

    Returns:
        Score in [0, 100].

    """
    today, value = _day(current.date), current.dfa_alpha1
    if not value or not math.isfinite(value) or value <= 0:
        return 50.0
    reference = [
        s.dfa_alpha1
        for _, day_sessions in _previous_days(baseline, today, baseline_days)
        for s in day_sessions
        if s.dfa_alpha1 and math.isfinite(s.dfa_alpha1) and s.dfa_alpha1 > 0
    ]
    return baseline_relative_score(value, reference, higher_is_better=False)


def ln_rmssd_trend_score(
    current: HRVFeatures,
    baseline,
    *,
    window: int = WINDOW_DAYS,
    min_count: int = MIN_MEASURES,
    baseline_days: int = BASELINE_DAYS,
    factor: float = SWC_FACTOR,
) -> float:
    """Trend component of the readiness score, in [0, 100].

    Change of the 7-day rolling mean of lnRMSSD versus the previous week,
    expressed in SWC units ``x = (mean_7d(today) − mean_7d(today − 7)) / SWC``:

    * inside ±1 SWC (normal fluctuation) → 50;
    * beyond, ``50 ± 50 × tanh(|x| − 1)`` — a sustained rise of 2 SWC gives
      ≈ 88, a decline of 2 SWC ≈ 12;
    * 50 (neutral) with less than 14 days since the first measurement, or
      when either week has fewer than 3 measurements or the baseline fewer
      than 6.

    Args:
        current: Session being scored (its ``date`` is required).
        baseline: Previous sessions (``Baseline`` — ``poor`` excluded — or a
            list of ``HRVFeatures``).
        window: Rolling window (days).
        min_count: Minimum measurements per window.
        baseline_days: SWC baseline length (days).
        factor: SWC factor.

    Returns:
        Trend score in [0, 100]; 50 = neutral.

    """
    today = _day(current.date)
    if today is None:
        return 50.0
    daily = daily_ln_rmssd([*_sessions(baseline), current])
    if not daily or daily[0][0] > today - timedelta(days=2 * window - 1):
        return 50.0  # less than two full weeks of history
    now, _ = _mean_cv(_window(daily, today, window), min_count)
    before, _ = _mean_cv(
        _window(daily, today - timedelta(days=window), window), min_count
    )
    band = _swc_band(
        daily,
        today - timedelta(days=window),
        factor,
        baseline_days,
        MIN_BASELINE_MEASURES,
    )
    if (
        band is None
        or band.swc <= 0
        or not (math.isfinite(now) and math.isfinite(before))
    ):
        return 50.0
    x = (now - before) / band.swc
    excess = math.copysign(max(abs(x) - 1.0, 0.0), x)
    return float(50.0 + 50.0 * math.tanh(excess))
