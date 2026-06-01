"""TRIMP computation and readiness loading for the training load model.

Two TRIMP formulas are provided:

* :func:`trimp_hrv_based` — HRV-readiness-weighted TRIMP. Primary method
  when a daily HRV protocol is in place. The readiness score is computed
  from the protocol that was chosen as primary for the user (``"resting"``
  or ``"orthostatic"``); the two are never mixed (see protocol consistency
  rule in ``docs/training_load/atl_ctl_tsb.md``).
* :func:`trimp_banister` — Classical Banister (1991) formula using effort HR
  from a sensor. Fallback when no HRV readiness is available.

Loading readiness from the database:

* :func:`load_readiness_for_date` — strict, single-protocol lookup.
  Returns ``None`` when no session is found for the requested date.
  Never falls back to the other protocol.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_oura

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


def load_readiness_for_date(
    user_id: str,
    date: str,
    repo: HRVRepository,
    baseline: Baseline,
    protocol: Literal["resting", "orthostatic"],
) -> float | None:
    """Load the readiness score for a given date from the database.

    Looks up the HRV session recorded on ``date`` and computes a readiness
    score relative to ``baseline`` using :func:`readiness_score_oura`.

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
            **same protocol**. Must not mix resting and orthostatic sessions.
        protocol: Primary protocol to read from.

    Returns:
        Readiness score in [0, 100] if a session exists for ``date``,
        ``None`` otherwise.

    """
    target = date[:10]

    if protocol == "resting":
        for feat in repo.load_features(user_id):
            if feat.date and str(feat.date)[:10] == target:
                return readiness_score_oura(feat, baseline)
        return None

    # protocol == "orthostatic": use the supine phase as the readiness input
    for record in repo.load_orthostatic(user_id):
        if str(record.date)[:10] == target:
            return readiness_score_oura(record.supine, baseline)
    return None
