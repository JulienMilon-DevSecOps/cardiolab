"""Multivariate anomaly detection — Mahalanobis distance to the personal cloud.

:func:`~cardiolab.analytics.anomaly.detect_rmssd_anomaly` looks at one metric.
A morning can have a normal RMSSD and still be unusual: resting heart rate
high *and* DFA α1 low, each within its own range, but together unlike any
usual morning. The Mahalanobis distance measures how far a session lies from
the athlete's usual cloud of sessions, taking the correlations between the
metrics into account (a low RMSSD with a high heart rate is expected; a high
RMSSD with a high heart rate is not).

Choices:

* **Metrics**: the four components of the readiness score —
  ``ln_rmssd``, ``mean_hr``, ``dfa_alpha1``, ``sd_ratio``. Near-duplicates
  (SD1 = RMSSD/√2, pNN50) are left out: they make the covariance unstable.
* **Reference**: the sessions of the 90 days before the session (never the
  session itself nor later ones), ``poor`` signal quality excluded by
  :class:`~cardiolab.analytics.baseline.Baseline`; at least 40 sessions.
* **Robust reference** (:func:`robust_covariance`): a few sick mornings
  already in the reference would widen a classical covariance and hide the
  next ones (masking). A Minimum Covariance Determinant (Rousseeuw 1984;
  FAST-MCD, Rousseeuw & Van Driessen 1999) finds the core of the cloud; the
  sessions far outside it (beyond the 99.9 % χ² quantile) are set aside and
  the cloud is the classical mean and covariance of the others. Random
  starts use a fixed seed — results are reproducible.
* **Threshold** (:func:`prediction_threshold`): the 97.5 % quantile of the
  distance of a *new* session to a cloud estimated from *n* sessions
  (Hotelling's T² prediction law, an F law). With few sessions it is wider
  than the asymptotic χ² threshold (distance 3.34 for 4 metrics): 3.75
  with 40 sessions, 3.51 with 90.
* **Explanation**: the z-score of each metric against the cloud and the one
  that deviates most (``main_driver``) — an alert must say what is unusual.

Calibration (simulated normal clouds, 4 correlated metrics, 40 runs each):
false alarms 4.3 % with 40 reference sessions, 2.7 % with 60, 2.6 % with 90
(nominal 2.5 %), unchanged when 10–20 % of the reference sessions are
outliers — where a classical covariance stops detecting anything. With 30
sessions false alarms reach about 6 %, hence the minimum of 40.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from scipy import stats

from cardiolab.analytics.monitoring import _day, _sessions

DEFAULT_FEATURES: tuple[str, ...] = ("ln_rmssd", "mean_hr", "dfa_alpha1", "sd_ratio")
"""Readiness-score components used by default."""

REFERENCE_DAYS = 90
"""Days before the session used as the reference."""

MIN_REFERENCE_SESSIONS = 40
"""Fewer reference sessions → ``insufficient_data``."""

DEFAULT_QUANTILE = 0.975
"""Quantile of the default threshold."""

SCREEN_QUANTILE = 0.999
"""χ² quantile beyond which a reference session is set aside."""

_N_STARTS = 30
_MAX_C_STEPS = 30


# ======================
# ROBUST COVARIANCE
# ======================


@dataclass
class RobustEstimate:
    """Centre and covariance of a reference cloud (:func:`robust_covariance`).

    Attributes:
        centre: Mean of the retained sessions, shape ``(p,)``.
        covariance: Covariance of the retained sessions, shape ``(p, p)``.
        support: ``True`` for each retained session, shape ``(n,)``.

    """

    centre: np.ndarray
    covariance: np.ndarray
    support: np.ndarray

    @property
    def n_used(self) -> int:
        """Number of retained sessions."""
        return int(self.support.sum())


def robust_covariance(data: np.ndarray, *, seed: int = 0) -> RobustEstimate:
    """Centre and covariance of a cloud, outlying sessions set aside.

    1. FAST-MCD (Rousseeuw & Van Driessen 1999): from random subsets of
       ``p + 1`` sessions, "C-steps" keep the ``h = (n + p + 1) / 2``
       sessions closest to the current estimate; the subset with the
       smallest covariance determinant is the core of the cloud. Its
       covariance is scaled to be consistent under normality.
    2. Screening: the sessions beyond the 99.9 % χ² quantile are set aside,
       the classical mean and covariance of the others are computed (with
       the consistency factor of that truncation), and the screening is
       repeated until the retained set no longer changes.

    The core alone under-estimates the spread with few sessions (many false
    alarms); the screened classical estimate keeps the robustness and is
    calibrated (module docstring).

    Args:
        data: ``(n, p)`` array, one row per session, no missing value.
        seed: Seed of the random starts.

    Returns:
        :class:`RobustEstimate`.

    Raises:
        ValueError: If ``data`` is not 2-D, contains non-finite values, has
            fewer rows than ``p + 2``, or a metric does not vary.

    """
    x = np.asarray(data, dtype=float)
    if x.ndim != 2:
        raise ValueError("data must be a 2-D array (sessions × metrics)")
    if not np.all(np.isfinite(x)):
        raise ValueError("data must not contain missing values")
    n, p = x.shape
    if n < p + 2:
        raise ValueError(
            f"At least {p + 2} sessions are needed for {p} metrics, got {n}"
        )
    h = (n + p + 1) // 2

    rng = np.random.default_rng(seed)
    best_det, best_subset = np.inf, None
    for _ in range(_N_STARTS):
        subset, det = _c_steps(x, rng.choice(n, size=p + 1, replace=False), h)
        if det < best_det:
            best_det, best_subset = det, subset
    if best_subset is None:
        raise ValueError(
            "A metric does not vary across the sessions: covariance is singular"
        )

    centre = x[best_subset].mean(axis=0)
    cov = np.cov(x[best_subset], rowvar=False).reshape(p, p)
    cov = cov * np.median(_squared_distances(x, centre, cov)) / stats.chi2.ppf(0.5, p)

    cut = stats.chi2.ppf(SCREEN_QUANTILE, p)
    factor = stats.chi2.cdf(cut, p) / stats.chi2.cdf(cut, p + 2)
    keep = np.ones(n, dtype=bool)
    for _ in range(_MAX_C_STEPS):
        new_keep = _squared_distances(x, centre, cov) <= cut
        if new_keep.sum() < p + 2:
            break
        centre = x[new_keep].mean(axis=0)
        cov = np.cov(x[new_keep], rowvar=False).reshape(p, p) * factor
        if np.array_equal(new_keep, keep):
            break
        keep = new_keep
    if not np.linalg.det(cov) > 0:
        raise ValueError(
            "A metric does not vary across the sessions: covariance is singular"
        )
    return RobustEstimate(centre=centre, covariance=cov, support=keep)


def _c_steps(x: np.ndarray, subset: np.ndarray, h: int) -> tuple[np.ndarray, float]:
    """Iterate C-steps from ``subset``; return the final subset and its determinant.

    Each step keeps the ``h`` points closest to the estimate of the current
    subset: the determinant never increases, and the subset stops changing
    after a few steps.
    """
    subset = np.sort(subset)
    for _ in range(_MAX_C_STEPS):
        centre = x[subset].mean(axis=0)
        cov = np.atleast_2d(np.cov(x[subset], rowvar=False))
        if not np.linalg.det(cov) > 0:
            return subset, np.inf
        new_subset = np.sort(
            np.argsort(_squared_distances(x, centre, cov), kind="stable")[:h]
        )
        if np.array_equal(new_subset, subset):
            break
        subset = new_subset
    det = float(np.linalg.det(np.atleast_2d(np.cov(x[subset], rowvar=False))))
    return subset, det if det > 0 else np.inf


def _squared_distances(
    x: np.ndarray, centre: np.ndarray, cov: np.ndarray
) -> np.ndarray:
    """Squared Mahalanobis distance of each row of ``x``."""
    diff = np.atleast_2d(x) - centre
    return np.einsum("ij,ij->i", diff, np.linalg.solve(cov, diff.T).T)


# ======================
# DISTANCE
# ======================


def mahalanobis_distance(
    reference: np.ndarray,
    point: np.ndarray,
    *,
    robust: bool = True,
    seed: int = 0,
) -> float:
    """Mahalanobis distance of ``point`` to the cloud of ``reference``.

    Args:
        reference: ``(n, p)`` array of previous sessions.
        point: ``(p,)`` values of the session to evaluate.
        robust: Outlying reference sessions set aside
            (:func:`robust_covariance`); ``False`` for the classical mean and
            covariance of all of them.
        seed: Seed of the robust estimate.

    Returns:
        Distance (≥ 0, in "standard deviations" of the cloud).

    Raises:
        ValueError: On shape mismatch, missing values, too few sessions or a
            singular covariance.

    """
    ref = np.asarray(reference, dtype=float)
    pt = np.asarray(point, dtype=float).ravel()
    if ref.ndim != 2 or ref.shape[1] != pt.size:
        raise ValueError("point must have one value per column of reference")
    if not np.all(np.isfinite(pt)):
        raise ValueError("point must not contain missing values")
    est = robust_covariance(ref, seed=seed) if robust else _classical(ref)
    return float(np.sqrt(_squared_distances(pt, est.centre, est.covariance)[0]))


def _classical(ref: np.ndarray) -> RobustEstimate:
    if ref.ndim != 2 or not np.all(np.isfinite(ref)):
        raise ValueError("data must be a 2-D array without missing values")
    n, p = ref.shape
    if n < p + 2:
        raise ValueError(
            f"At least {p + 2} sessions are needed for {p} metrics, got {n}"
        )
    cov = np.cov(ref, rowvar=False).reshape(p, p)
    if np.linalg.matrix_rank(cov) < p:
        raise ValueError(
            "A metric does not vary across the sessions: covariance is singular"
        )
    return RobustEstimate(
        centre=ref.mean(axis=0), covariance=cov, support=np.ones(n, bool)
    )


def chi2_threshold(n_features: int, quantile: float = DEFAULT_QUANTILE) -> float:
    """Asymptotic distance threshold: √ of the χ² quantile (``n_features`` d.o.f.).

    The limit of :func:`prediction_threshold` for a cloud of infinitely many
    sessions (3.34 for 4 metrics at 97.5 %).
    """
    return float(np.sqrt(stats.chi2.ppf(quantile, n_features)))


def prediction_threshold(
    n_sessions: int, n_features: int, quantile: float = DEFAULT_QUANTILE
) -> float:
    """Distance threshold for a new session against a cloud of ``n_sessions``.

    A new session independent of the *n* reference sessions, all from the
    same normal law, has a squared distance distributed as
    ``p (n − 1)(n + 1) / (n (n − p)) · F(p, n − p)`` (Hotelling's T²
    prediction law). Returns the square root of its ``quantile``.

    Raises:
        ValueError: If ``n_sessions <= n_features``.

    """
    n, p = n_sessions, n_features
    if n <= p:
        raise ValueError(f"More than {p} sessions are needed, got {n}")
    scale = p * (n - 1) * (n + 1) / (n * (n - p))
    return float(np.sqrt(scale * stats.f.ppf(quantile, p, n - p)))


# ======================
# SESSION
# ======================


@dataclass
class MultivariateAnomaly:
    """Result of :func:`is_multivariate_anomaly` for one session.

    Attributes:
        status: ``"normal"``, ``"anomaly"``, ``"insufficient_data"`` (fewer
            than ``min_sessions`` reference sessions), ``"missing_features"``
            (a metric of the session is missing) or ``"no_variability"``
            (a metric does not vary in the reference).
        distance: Robust Mahalanobis distance; ``nan`` when not computed.
        threshold: Distance above which the session is an anomaly; ``nan``
            when not computed.
        n_reference: Reference sessions with every metric.
        n_used: Reference sessions kept in the cloud (outlying ones set
            aside, see :func:`robust_covariance`).
        features: Metrics used, in order.
        z_scores: z-score of each metric against the cloud,
            (value − centre) / SD.
        main_driver: Metric with the largest absolute z-score, or ``None``.

    """

    status: str
    distance: float = float("nan")
    threshold: float = float("nan")
    n_reference: int = 0
    n_used: int = 0
    features: tuple[str, ...] = DEFAULT_FEATURES
    z_scores: dict[str, float] = field(default_factory=dict)
    main_driver: str | None = None

    @property
    def is_anomaly(self) -> bool:
        """``True`` when the distance exceeds the threshold."""
        return self.status == "anomaly"

    def to_dict(self) -> dict:
        """Plain dict (``z_scores`` flattened to ``z_<metric>`` keys)."""
        out = {
            "status": self.status,
            "distance": self.distance,
            "threshold": self.threshold,
            "is_anomaly": self.is_anomaly,
            "n_reference": self.n_reference,
            "n_used": self.n_used,
            "main_driver": self.main_driver,
        }
        out.update({f"z_{k}": v for k, v in self.z_scores.items()})
        return out


def _vector(session, features: tuple[str, ...]) -> np.ndarray:
    values = []
    for name in features:
        v = getattr(session, name, None)
        values.append(float(v) if v is not None else np.nan)
    v = np.array(values)
    # 0.0 is the "not computed" default of HRVFeatures (no real session has
    # a heart rate, lnRMSSD, DFA α1 or SD ratio of exactly 0)
    v[v == 0.0] = np.nan
    return v


def _reference(baseline, today: date | None, days: int) -> list:
    sessions = _sessions(baseline)
    if today is None:
        return sessions
    start = today - timedelta(days=days)
    return [
        s for s in sessions if (d := _day(s.date)) is not None and start <= d < today
    ]


def is_multivariate_anomaly(
    current,
    baseline,
    *,
    features: tuple[str, ...] | list[str] = DEFAULT_FEATURES,
    days: int = REFERENCE_DAYS,
    min_sessions: int = MIN_REFERENCE_SESSIONS,
    threshold: float | None = None,
    seed: int = 0,
) -> MultivariateAnomaly:
    """Whether a session is atypical on several metrics at once.

    Args:
        current: ``HRVFeatures`` of the session to evaluate (dated).
        baseline: :class:`~cardiolab.analytics.baseline.Baseline` (``poor``
            sessions excluded) or list of ``HRVFeatures``.
        features: Metrics (``HRVFeatures`` attributes).
        days: Reference period before the session's date; undated session:
            the whole history.
        min_sessions: Minimum number of reference sessions with every metric.
        threshold: Distance threshold; default :func:`prediction_threshold`
            for the retained sessions (97.5 %; 3.75 with 40 sessions and 4
            metrics, 3.51 with 90).
        seed: Seed of the robust estimate.

    Returns:
        :class:`MultivariateAnomaly`.

    """
    feats = tuple(features)
    point = _vector(current, feats)
    if not np.all(np.isfinite(point)):
        return MultivariateAnomaly("missing_features", features=feats)
    rows = [_vector(s, feats) for s in _reference(baseline, _day(current.date), days)]
    rows = [r for r in rows if np.all(np.isfinite(r))]
    if len(rows) < max(min_sessions, len(feats) + 2):
        return MultivariateAnomaly(
            "insufficient_data", n_reference=len(rows), features=feats
        )
    try:
        est = robust_covariance(np.vstack(rows), seed=seed)
        distance = float(
            np.sqrt(_squared_distances(point, est.centre, est.covariance)[0])
        )
    except (ValueError, np.linalg.LinAlgError):
        return MultivariateAnomaly(
            "no_variability", n_reference=len(rows), features=feats
        )
    limit = (
        threshold
        if threshold is not None
        else prediction_threshold(est.n_used, len(feats))
    )
    centre, cov = est.centre, est.covariance
    sd = np.sqrt(np.diag(cov))
    z = (point - centre) / sd
    z_scores = {name: float(v) for name, v in zip(feats, z, strict=True)}
    return MultivariateAnomaly(
        "anomaly" if distance > limit else "normal",
        distance=distance,
        threshold=limit,
        n_reference=len(rows),
        n_used=est.n_used,
        features=feats,
        z_scores=z_scores,
        main_driver=feats[int(np.argmax(np.abs(z)))],
    )


# ======================
# REPORT
# ======================


def anomaly_report(
    history,
    *,
    features: tuple[str, ...] | list[str] = DEFAULT_FEATURES,
    days: int = REFERENCE_DAYS,
    min_sessions: int = MIN_REFERENCE_SESSIONS,
    threshold: float | None = None,
    seed: int = 0,
):
    """One row per dated session: univariate and multivariate anomaly.

    Each session is compared with the sessions before it only — the report
    reads like it would have day after day.

    Args:
        history: :class:`~cardiolab.analytics.baseline.Baseline` or list of
            dated ``HRVFeatures``.
        features: Metrics (see :func:`is_multivariate_anomaly`).
        days: Reference period before each session.
        min_sessions: Minimum number of reference sessions.
        threshold: Distance threshold; default :func:`prediction_threshold`.
        seed: Seed of the robust estimate.

    Returns:
        ``pandas.DataFrame`` with columns ``date``, ``zscore`` (lnRMSSD
        z-score of :func:`~cardiolab.analytics.anomaly.detect_rmssd_anomaly`,
        ``nan`` when not computed), ``mahalanobis``, ``threshold``,
        ``is_anomaly``, ``status``, ``main_driver`` and one ``z_<metric>``
        column per metric.

    Raises:
        ImportError: If ``pandas`` is not installed
            (``pip install cardiolab[analysis]``).

    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required for anomaly_report(). "
            "Install it with: pip install cardiolab[analysis]"
        ) from exc
    from cardiolab.analytics.anomaly import detect_rmssd_anomaly

    feats = tuple(features)
    sessions = sorted(
        (s for s in _sessions(history) if _day(s.date) is not None),
        key=lambda s: _day(s.date),
    )
    rows = []
    for s in sessions:
        res = is_multivariate_anomaly(
            s,
            sessions,
            features=feats,
            days=days,
            min_sessions=min_sessions,
            threshold=threshold,
            seed=seed,
        )
        uni = detect_rmssd_anomaly(s, sessions, method="zscore")
        row = {
            "date": str(s.date)[:10],
            "zscore": uni.get("z", np.nan),
            "mahalanobis": res.distance,
            "threshold": res.threshold,
            "is_anomaly": res.is_anomaly,
            "status": res.status,
            "main_driver": res.main_driver,
        }
        row.update({f"z_{f}": res.z_scores.get(f, np.nan) for f in feats})
        rows.append(row)
    columns = [
        "date",
        "zscore",
        "mahalanobis",
        "threshold",
        "is_anomaly",
        "status",
        "main_driver",
        *[f"z_{f}" for f in feats],
    ]
    return pd.DataFrame(rows, columns=columns)
