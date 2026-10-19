"""TRIMP computation, ATL/CTL/TSB model, and readiness loading.

Three load formulas are provided:

* :func:`trimp_hrv_based` — HRV-readiness-weighted TRIMP. Primary method
  when a daily HRV protocol is in place. The readiness score is computed
  from the protocol that was chosen as primary for the user (``"resting"``
  or ``"orthostatic"``); the two are never mixed (see protocol consistency
  rule in ``docs/training_load/atl_ctl_tsb.md``).
* :func:`trimp_banister` — Classical Banister (1991) formula using effort HR
  from a sensor. Fallback when no HRV readiness is available.
* :func:`trimp_session_rpe` — session RPE (Foster et al. 2001): duration ×
  perceived effort on the CR-10 scale. Valid for every sport, no heart rate
  needed (strength, intervals, team sports).

The three formulas have **different scales** — use one method consistently
for a given athlete's ATL / CTL / TSB.

ATL / CTL / TSB — Banister impulse-response model:

* :func:`compute_atl` — 7-day EMA of TRIMP (acute fatigue).
* :func:`compute_ctl` — 42-day EMA of TRIMP (chronic fitness).
* :func:`compute_tsb` — TSB = CTL − ATL (form / freshness).
* :class:`TrainingLoad` — end-to-end container: builds a dense daily series
  from ``load_training_sessions()`` output and exposes the ATL/CTL/TSB
  arrays plus a pandas DataFrame export.

Loading readiness from the database:

* :func:`load_readiness_for_date` — strict, single-protocol lookup.
  Returns ``None`` when no session is found for the requested date.
  Never falls back to the other protocol.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date as _date
from datetime import timedelta
from typing import TYPE_CHECKING, Literal

import numpy as np
from scipy.signal import lfilter

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import (
    orthostatic_readiness_score,
    readiness_score_multi,
)

if TYPE_CHECKING:
    from cardiolab.database.repository import HRVRepository


def trimp_hrv_based(duration_min: float, readiness_score: float) -> float:
    """Compute a TRIMP using the HRV readiness score.

    Formula: ``TRIMP = duration_min × (1 − readiness_score / 100)``.

    The readiness score drives the load factor: a fully recovered athlete
    (readiness = 100) produces zero cost for any workout; a severely stressed
    athlete (readiness = 0) produces maximum cost equal to the session
    duration in minutes.

    Args:
        duration_min: Workout duration in minutes. Must be strictly positive.
        readiness_score: Daily readiness in [0, 100] from the HRV protocol.
            50 is neutral (at baseline); > 50 is above baseline.

    Returns:
        TRIMP as a non-negative float (dimensionless).

    Raises:
        ValueError: If ``duration_min`` ≤ 0 or ``readiness_score`` is outside
            [0, 100].

    References:
        Manzi V et al. (2009). Dose–response relationship of autonomic nervous
        system responses to individualized training impulse in marathon runners.
        *J Strength Cond Res*, 23(9), 2722–2729.

    """
    if duration_min <= 0.0:
        raise ValueError(f"duration_min must be > 0, got {duration_min}")
    if not (0.0 <= readiness_score <= 100.0):
        raise ValueError(f"readiness_score must be in [0, 100], got {readiness_score}")
    return duration_min * (1.0 - readiness_score / 100.0)


def trimp_banister(
    duration_min: float,
    hr_mean: float,
    hr_max: float,
    hr_rest: float,
    sex: Literal["male", "female"] = "male",
) -> float:
    """Compute a TRIMP using the Banister (1991) heart rate reserve formula.

    Formula::

        HRR = (hr_mean − hr_rest) / (hr_max − hr_rest)
        TRIMP = duration_min × HRR × exp(b × HRR)

    where ``b = 1.92`` for males and ``b = 1.67`` for females (sex-specific
    weighting constants from Banister 1991).

    Requires an HR monitor that provides mean effort HR. Intended as a
    fallback when no HRV readiness is available.

    Args:
        duration_min: Workout duration in minutes. Must be strictly positive.
        hr_mean: Mean heart rate during the session (bpm).
        hr_max: Maximal heart rate of the athlete (bpm). Must be > ``hr_rest``.
        hr_rest: Resting heart rate of the athlete (bpm).
        sex: ``"male"`` (default) or ``"female"`` — selects the ``b``
            coefficient from Banister 1991.

    Returns:
        TRIMP as a non-negative float (dimensionless).

    Raises:
        ValueError: If ``duration_min`` ≤ 0 or ``hr_max`` ≤ ``hr_rest``.

    References:
        Banister EW. (1991). Modeling elite athletic performance. In:
        *Physiological Testing of the High-Performance Athlete*. Human
        Kinetics, pp. 403–424.

    """
    if duration_min <= 0.0:
        raise ValueError(f"duration_min must be > 0, got {duration_min}")
    if hr_max <= hr_rest:
        raise ValueError(f"hr_max ({hr_max}) must be greater than hr_rest ({hr_rest})")
    b = 1.92 if sex == "male" else 1.67
    hrr = (hr_mean - hr_rest) / (hr_max - hr_rest)
    hrr = max(0.0, min(1.0, hrr))
    return duration_min * hrr * math.exp(b * hrr)


RPE_SCALE: dict[int, str] = {
    0: "Rest",
    1: "Very, very easy",
    2: "Easy",
    3: "Moderate",
    4: "Somewhat hard",
    5: "Hard",
    6: "Hard",
    7: "Very hard",
    8: "Very hard",
    9: "Very hard",
    10: "Maximal",
}
"""CR-10 scale used for session RPE (Foster et al. 2001, after Borg)."""


def validate_rpe(rpe) -> int | None:
    """Check a session RPE: an integer between 0 and 10, or ``None`` (not entered).

    Args:
        rpe: Perceived effort of the whole session on the CR-10 scale.

    Returns:
        The RPE as an ``int``, or ``None``.

    Raises:
        ValueError: If ``rpe`` is not a whole number between 0 and 10.

    """
    if rpe is None:
        return None
    if isinstance(rpe, bool) or not isinstance(rpe, (int, float)) or rpe != int(rpe):
        raise ValueError(f"rpe must be a whole number between 0 and 10, got {rpe!r}")
    if not 0 <= rpe <= 10:
        raise ValueError(f"rpe must be between 0 and 10, got {rpe}")
    return int(rpe)


def trimp_session_rpe(duration_min: float, rpe: int) -> float:
    """Compute the session-RPE training load (Foster et al. 2001).

    Formula::

        load = duration_min × RPE

    The athlete rates the **whole session** about 30 minutes after it ends,
    on the CR-10 scale (:data:`RPE_SCALE`: 0 rest … 10 maximal). Simple,
    valid for every sport and without heart rate — strength training, short
    intervals and team sports, where heart-rate methods underestimate the
    load. Expressed in arbitrary units (AU): a 60-minute session rated 5
    gives 300 AU.

    The scale differs from :func:`trimp_hrv_based` and :func:`trimp_banister`:
    use one method consistently for a given athlete's ATL / CTL / TSB.

    Args:
        duration_min: Session duration in minutes. Must be strictly positive.
        rpe: Perceived effort, whole number from 0 to 10.

    Returns:
        Session load in arbitrary units.

    Raises:
        ValueError: If ``duration_min`` ≤ 0 or ``rpe`` is not 0–10.

    References:
        Foster, C., Florhaug, J. A., Franklin, J., Gottschall, L., Hrovatin,
        L. A., Parker, S., Doleshal, P., & Dodge, C. (2001). A new approach to
        monitoring exercise training. *Journal of Strength and Conditioning
        Research*, 15(1), 109–115.

    """
    if duration_min <= 0.0:
        raise ValueError(f"duration_min must be > 0, got {duration_min}")
    value = validate_rpe(rpe)
    if value is None:
        raise ValueError("rpe is required for the session-RPE load")
    return float(duration_min * value)


LOAD_METHODS: tuple[str, ...] = ("hrv", "banister", "rpe")
"""Load methods an athlete can choose (``user_profiles.load_method``)."""

LOAD_METHOD_REQUIREMENTS: dict[str, dict[str, str]] = {
    "hrv": {
        "session": "duration",
        "other": "the morning measurement of the same day (score de forme of the main protocol)",
    },
    "banister": {
        "session": "duration, mean heart rate of the session",
        "other": "profile: maximal HR, resting HR, sex",
    },
    "rpe": {
        "session": "duration, perceived effort 0–10 rated about 30 minutes after the session",
        "other": "—",
    },
}
"""Minimum data of each load method — without them the load stays pending (``None``)."""


def validate_load_method(method: str) -> str:
    """Check a load method name.

    Args:
        method: ``"hrv"`` (score de forme of the day), ``"banister"`` (session
            heart rate) or ``"rpe"`` (perceived effort).

    Returns:
        The method.

    Raises:
        ValueError: If the method is unknown.

    """
    if method not in LOAD_METHODS:
        raise ValueError(
            f"Unknown load method {method!r}. Choose from {', '.join(LOAD_METHODS)}."
        )
    return method


def session_load(
    method: str,
    duration_min: float | None,
    *,
    readiness: float | None = None,
    hr_mean: float | None = None,
    hr_max: float | None = None,
    hr_rest: float | None = None,
    sex: str | None = "male",
    rpe: int | None = None,
) -> float | None:
    """Load of one session with the athlete's method — ``None`` when data is missing.

    One method per athlete (``user_profiles.load_method``), applied to every
    session so that ATL / CTL / TSB stay on one scale:

    * ``"hrv"`` — :func:`trimp_hrv_based` (needs the day's ``readiness``);
    * ``"banister"`` — :func:`trimp_banister` (needs ``hr_mean``, ``hr_max``,
      ``hr_rest``);
    * ``"rpe"`` — :func:`trimp_session_rpe` (needs ``rpe``).

    A session without the data its method needs is **pending** (``None``):
    its load is never computed with another method.

    Args:
        method: Load method (:data:`LOAD_METHODS`).
        duration_min: Session duration in minutes.
        readiness: Score de forme of the day (``"hrv"``).
        hr_mean: Mean HR of the session (``"banister"``).
        hr_max: Maximal HR of the athlete (``"banister"``).
        hr_rest: Resting HR of the athlete (``"banister"``).
        sex: ``"male"`` / ``"female"`` (``"banister"`` coefficient).
        rpe: Perceived effort 0–10 (``"rpe"``).

    Returns:
        The load, or ``None`` when a required value is missing.

    Raises:
        ValueError: If ``method`` is unknown or a value is out of range.

    """
    validate_load_method(method)
    if not duration_min or duration_min <= 0:
        return None
    if method == "hrv":
        return None if readiness is None else trimp_hrv_based(duration_min, readiness)
    if method == "banister":
        if None in (hr_mean, hr_max, hr_rest):
            return None
        return trimp_banister(duration_min, hr_mean, hr_max, hr_rest, sex=sex or "male")
    return None if rpe is None else trimp_session_rpe(duration_min, rpe)


def load_readiness_for_date(
    user_id: str,
    date: str,
    repo: HRVRepository,
    baseline: Baseline | None,
    protocol: Literal["resting", "orthostatic"],
) -> float | None:
    """Load the readiness score for a given date from the database.

    Looks up the HRV session recorded on ``date`` and computes a readiness
    score relative to ``baseline`` with the same scorer as the one stored and
    displayed for that protocol, so that the TRIMP is built from the score the
    athlete actually sees:

    * ``"resting"`` → :func:`readiness_score_multi`;
    * ``"orthostatic"`` → :func:`orthostatic_readiness_score` (supine phase).

    Changed in 0.3.2: earlier versions used the legacy
    :func:`readiness_score_oura` (RMSSD 70 % + HR 30 %), which gave a
    different value from the displayed readiness score.

    Protocol consistency rule — the ``protocol`` parameter is **strict**:

    * ``"resting"`` → reads from the resting protocol table (``hrv_features``).
    * ``"orthostatic"`` → reads from the orthostatic table and uses the
      **supine phase** RMSSD, not the ΔHR score. The supine phase is
      physiologically equivalent to a resting measurement and produces
      meaningful day-to-day variability.

    The two protocols are **never** crossed. If the wrong protocol is
    specified, the session will not be found and ``None`` is returned.

    Args:
        user_id: Athlete identifier.
        date: ISO date string of the target session (``"YYYY-MM-DD"`` or
            ``"YYYY-MM-DDTHH:MM:SS"`` — only the date part is matched).
        repo: An open ``HRVRepository`` context (must be used inside a
            ``with`` block by the caller).
        baseline: Personal reference built from previous sessions of the
            **same protocol** (resting sessions, or supine phases). Must not mix
            resting and orthostatic sessions. ``None`` → the score stored with
            the session is returned (``score`` for resting, ``readiness_score``
            for orthostatic, cardiolab ≥ 0.5.0); ``None`` if not stored.
        protocol: Primary protocol to read from.

    Returns:
        Readiness score in [0, 100] if a session exists for ``date``,
        ``None`` otherwise.

    """
    if protocol == "resting":
        feat = repo.load_features_for_date(user_id, date)
        if feat is None:
            return None
        return feat.score if baseline is None else readiness_score_multi(feat, baseline)

    # protocol == "orthostatic": use the supine phase as the readiness input
    record = repo.load_orthostatic_for_date(user_id, date)
    if record is None:
        return None
    if baseline is None:
        return record.readiness_score
    return orthostatic_readiness_score(record.supine, baseline)


# ======================
# EMA — INTERNAL
# ======================


def _ema(trimp: np.ndarray, tau: int) -> np.ndarray:
    """Exponential moving average with time constant *tau* days.

    ``k = 1 − exp(−1/tau)``.  Each day:
    ``EMA[i] = trimp[i] * k + EMA[i-1] * (1 − k)``.

    Implemented as a first-order IIR filter via ``scipy.signal.lfilter``
    (numerator ``b=[k]``, denominator ``a=[1, -(1-k)]``) which is
    mathematically equivalent to the recurrence and vectorised in C.

    Args:
        trimp: Dense daily TRIMP array (one value per consecutive day).
        tau: Time constant in days (7 for ATL, 42 for CTL).

    Returns:
        Array of the same length as *trimp*.

    """
    k = 1.0 - math.exp(-1.0 / tau)
    return lfilter([k], [1.0, -(1.0 - k)], trimp)


# ======================
# PUBLIC EMA FUNCTIONS
# ======================


def compute_atl(trimp: np.ndarray, tau: int = 7) -> np.ndarray:
    """Compute the Acute Training Load (short-term fatigue) via 7-day EMA.

    ATL rises quickly during training blocks and decays fast during rest.
    It represents accumulated fatigue over the past ~7 days.

    The input must be a **dense** daily array — one TRIMP value per
    consecutive day, with ``0`` on rest days. Gaps in the series will
    produce incorrect results.

    Args:
        trimp: Dense daily TRIMP array, oldest first.
        tau: Time constant in days. Default 7 (standard ATL).

    Returns:
        ATL array of the same length as *trimp*. Initial condition: 0.

    References:
        Banister EW et al. (1975). *Aust J Sports Med*, 7, 57–61.
        Morton RH et al. (1990). *J Appl Physiol*, 69(3), 1171–1177.

    """
    return _ema(trimp, tau)


def compute_ctl(trimp: np.ndarray, tau: int = 42) -> np.ndarray:
    """Compute the Chronic Training Load (long-term fitness) via 42-day EMA.

    CTL responds slowly to daily changes, rising over training blocks lasting
    weeks or months and decaying slowly during detraining. It represents
    accumulated aerobic adaptation built by consistent training.

    CTL is not meaningful until ~6 weeks of data (one time constant).

    Args:
        trimp: Dense daily TRIMP array, oldest first.
        tau: Time constant in days. Default 42 (standard CTL).

    Returns:
        CTL array of the same length as *trimp*. Initial condition: 0.

    """
    return _ema(trimp, tau)


def compute_tsb(ctl: np.ndarray, atl: np.ndarray) -> np.ndarray:
    """Compute the Training Stress Balance (form) as CTL − ATL.

    TSB > 0 indicates the athlete is fresh (CTL > ATL — fitness exceeds
    fatigue).  TSB < 0 indicates accumulated fatigue. The optimal
    performance window is approximately TSB +5 to +25.

    Args:
        ctl: Chronic Training Load array.
        atl: Acute Training Load array. Must be the same length as *ctl*.

    Returns:
        TSB array of the same length as *ctl*.

    """
    return ctl - atl


# ======================
# TrainingLoad CLASS
# ======================


@dataclass
class TrainingLoad:
    """ATL / CTL / TSB time series computed from a session TRIMP history.

    Attributes:
        dates: Dense list of ISO date strings (one per consecutive day).
        trimp: Daily TRIMP values (0 on rest days or when readiness was absent).
        atl: Acute Training Load — 7-day EMA of TRIMP.
        ctl: Chronic Training Load — 42-day EMA of TRIMP.
        tsb: Training Stress Balance — CTL − ATL.

    """

    dates: list[str] = field(default_factory=list)
    trimp: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    atl: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    ctl: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    tsb: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))

    # ======================
    # FACTORY
    # ======================

    @classmethod
    def from_sessions(
        cls,
        sessions: list[dict],
        tau_atl: int = 7,
        tau_ctl: int = 42,
    ) -> TrainingLoad:
        """Build a TrainingLoad from a list of session dicts.

        The expected input is the output of
        ``HRVRepository.load_training_sessions()`` — a list of dicts with
        at least ``date`` (``"YYYY-MM-DD"``) and ``trimp`` (float or None)
        keys, sorted ascending by date.

        Processing steps:

        1. Aggregate TRIMP by date — **sum** across all activities on the
           same day (multiple activities = multiple rows with the same date).
           Activities with ``trimp=None`` contribute ``0`` to the sum.
        2. Find the earliest and latest dates across all activities.
        3. Build a dense daily date range between them (inclusive).
        4. Fill rest days (no activity logged) with ``0``.
        5. Compute ATL and CTL via :func:`compute_atl` / :func:`compute_ctl`.
        6. Compute TSB via :func:`compute_tsb`.

        Args:
            sessions: List of training session dicts, sorted by date ASC.
            tau_atl: ATL time constant in days (default 7).
            tau_ctl: CTL time constant in days (default 42).

        Returns:
            A populated :class:`TrainingLoad` instance.
            Returns an empty instance when *sessions* is empty.

        """
        if not sessions:
            return cls()

        # Aggregate TRIMP by date — sum across multiple activities per day.
        # An activity with trimp=None contributes 0 (TRIMP not yet computed).
        # This correctly handles the one-row-per-activity storage model where
        # the same date may appear multiple times (morning run + evening cycling).
        trimp_by_date: dict[str, float] = {}
        all_dates_seen: set[str] = set()
        for s in sessions:
            d = str(s["date"])[:10]
            all_dates_seen.add(d)
            t = float(s["trimp"]) if s["trimp"] is not None else 0.0
            trimp_by_date[d] = trimp_by_date.get(d, 0.0) + t

        first = _date.fromisoformat(min(all_dates_seen))
        last = _date.fromisoformat(max(all_dates_seen))
        n = (last - first).days + 1

        dates: list[str] = []
        trimp_array = np.zeros(n)
        for i in range(n):
            d = str(first + timedelta(days=i))
            dates.append(d)
            trimp_array[i] = trimp_by_date.get(d, 0.0)

        atl = compute_atl(trimp_array, tau=tau_atl)
        ctl = compute_ctl(trimp_array, tau=tau_ctl)
        tsb = compute_tsb(ctl, atl)

        return cls(dates=dates, trimp=trimp_array, atl=atl, ctl=ctl, tsb=tsb)

    # ======================
    # EXPORT
    # ======================

    def to_dataframe(self):
        """Return a pandas DataFrame with one row per day.

        Columns: ``date`` (str), ``trimp``, ``atl``, ``ctl``, ``tsb``
        (all float).

        Returns:
            A ``pandas.DataFrame`` sorted by ascending date.
            Returns an empty DataFrame when the instance is empty.

        Raises:
            ImportError: If pandas is not installed.
                Install with ``pip install cardiolab[analysis]``.

        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install cardiolab[analysis]"
            ) from exc

        if not self.dates:
            return pd.DataFrame(columns=["date", "trimp", "atl", "ctl", "tsb"])

        return pd.DataFrame(
            {
                "date": self.dates,
                "trimp": self.trimp,
                "atl": self.atl,
                "ctl": self.ctl,
                "tsb": self.tsb,
            }
        )
