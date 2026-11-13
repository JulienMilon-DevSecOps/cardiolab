"""Maximal heart rate — sustained peak, HRmax observed in sessions, profile update.

HRmax drives many calculations: the session heart-rate load (Banister), the
VO2max estimate (Uth), the LSCT targets (60 / 80 / 90 %) and the training
zones without thresholds. Predicted from the age (Tanaka: ``208 − 0.7 × age``)
it is off by about ±10 bpm for one person — almost a whole zone.

Three better sources, from the most to the least reliable:

* ``field_test`` — a maximal test (:mod:`cardiolab.protocols.hr_max_test`);
* ``provided`` — entered by the athlete (laboratory test, known value);
* ``observed`` — the highest heart rate **held 5 s** in the imported sessions
  (:func:`observed_hr_max`). A lower bound: the true HRmax is at least as high.

**Held 5 s**: a 3-sample median of the second-by-second heart rate (an
isolated spike or dip removed), then the minimum over each 5-s window, then
the highest of these. A value counts only if it was reached for the whole 5
seconds: a one- to four-second spike (a strap that touches badly, a wrist
sensor) never passes.

A new HRmax is only ever **proposed** (:func:`propose_hr_max_update`), with
what it changes — never applied silently, and never lowered from sessions.

References:
    Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal
    heart rate revisited. Journal of the American College of Cardiology,
    37(1), 153–156.

    Gillinov, S., et al. (2017). Variable accuracy of wearable heart rate
    monitors during aerobic exercise. Medicine & Science in Sports &
    Exercise, 49(8), 1697–1703.

"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np

from cardiolab.analytics.zones import five_zones_from_hr_max

HR_MAX_SOURCES: tuple[str, ...] = ("provided", "tanaka", "field_test", "observed")
"""Where the HRmax of a profile comes from (``user_profiles.hr_max_source``)."""

SUSTAINED_SEC = 5.0
"""Minimum duration (s) of a heart rate counted as reached."""

HR_PLAUSIBLE = (30.0, 230.0)
"""Heart rates outside this range (bpm) are discarded as sensor errors."""

MAX_JUMP_BPM = 25.0
"""A jump larger than this between two seconds is a sensor drop-out."""

UTH_FACTOR = 15.3
"""VO2max ≈ 15.3 × HRmax / HRrest (Uth et al. 2004)."""

LSCT_TARGET_PCT = (60.0, 80.0, 90.0)


def round_bpm(value: float) -> int:
    """Round a heart rate half up (166.5 → 167; Python's ``round`` gives 166)."""
    return int(math.floor(value + 0.5))


def validate_hr_max_source(source: str | None) -> None:
    """Raise ``ValueError`` when ``source`` is not ``None`` nor a known source."""
    if source is not None and source not in HR_MAX_SOURCES:
        raise ValueError(
            f"Unknown hr_max_source {source!r}; expected one of {HR_MAX_SOURCES}."
        )


def clean_heart_rate(time_sec, heart_rate) -> tuple[np.ndarray, np.ndarray]:
    """Return the samples with a plausible heart rate, without drop-out jumps.

    Args:
        time_sec: Time of each sample (s), increasing.
        heart_rate: Heart rate of each sample (bpm); ``nan`` for missing.

    Returns:
        ``(time_sec, heart_rate)`` without the samples outside 30–230 bpm and
        without those reached by a jump of more than 25 bpm in one second.

    Raises:
        ValueError: If the two arrays differ in length.

    """
    t = np.asarray(time_sec, dtype=float)
    hr = np.asarray(heart_rate, dtype=float)
    if t.shape != hr.shape:
        raise ValueError("time_sec and heart_rate must have the same length")
    keep = (
        np.isfinite(t)
        & np.isfinite(hr)
        & (hr >= HR_PLAUSIBLE[0])
        & (hr <= HR_PLAUSIBLE[1])
    )
    t, hr = t[keep], hr[keep]
    if len(hr) > 1:
        dt = np.maximum(np.diff(t), 1.0)
        jump = np.abs(np.diff(hr)) / dt > MAX_JUMP_BPM
        ok = np.r_[True, ~jump]
        t, hr = t[ok], hr[ok]
    return t, hr


def held_heart_rate(
    time_sec, heart_rate, window_sec: float = SUSTAINED_SEC
) -> np.ndarray:
    """Return, at each sample, the heart rate held for the ``window_sec`` around it.

    A 3-sample median first removes isolated beats (a single spike or dip),
    then the minimum over the centred ``window_sec`` window keeps only what
    was reached during the **whole** window. A window with less than
    ``window_sec`` of data (start, end, gaps) is ``nan``.

    Args:
        time_sec: Time of each sample (s), increasing.
        heart_rate: Heart rate (bpm), about one sample per second.
        window_sec: Duration a value must be held (s).

    Returns:
        The held heart rate, same length as the input.

    """
    t = np.asarray(time_sec, dtype=float)
    hr = np.asarray(heart_rate, dtype=float)
    n = len(hr)
    out = np.full(n, math.nan)
    if n < 3:
        return out
    smooth = hr.copy()
    smooth[1:-1] = np.median(np.vstack([hr[:-2], hr[1:-1], hr[2:]]), axis=0)
    half = window_sec / 2.0
    lo = np.searchsorted(t, t - half, side="left")
    hi = np.searchsorted(t, t + half, side="right")
    for i in range(n):
        a, b = lo[i], hi[i]
        if b - a >= 2 and t[b - 1] - t[a] >= window_sec - 1.0:
            gaps = np.diff(t[a:b])
            if gaps.size and gaps.max() <= 2.0:
                out[i] = float(np.min(smooth[a:b]))
    return out


@dataclass
class SustainedPeak:
    """Highest heart rate held for ``window_sec``.

    Attributes:
        hr_max: The highest heart rate held for the whole window (bpm),
            ``nan`` without data.
        time_sec: When it was reached (centre of the window).
        raw_max: The highest single sample within 30–230 bpm, before the
            drop-out filter (bpm).
        window_sec: Duration a value must be held (s).

    """

    hr_max: float
    time_sec: float
    raw_max: float
    window_sec: float = SUSTAINED_SEC

    @property
    def isolated_spike(self) -> bool:
        """``True`` when the raw maximum exceeds the held one by more than 5 bpm."""
        return math.isfinite(self.raw_max) and self.raw_max - self.hr_max > 5.0


def sustained_peak(
    time_sec, heart_rate, *, window_sec: float = SUSTAINED_SEC
) -> SustainedPeak:
    """Find the highest heart rate held for ``window_sec`` (5 s by default).

    Args:
        time_sec: Time of each sample (s).
        heart_rate: Heart rate (bpm), second by second.
        window_sec: Duration a value must be held.

    Returns:
        A :class:`SustainedPeak` (``hr_max = nan`` when no window is complete).

    """
    raw = np.asarray(heart_rate, dtype=float)
    plausible = raw[
        np.isfinite(raw) & (raw >= HR_PLAUSIBLE[0]) & (raw <= HR_PLAUSIBLE[1])
    ]
    raw_max = float(plausible.max()) if plausible.size else math.nan
    t, hr = clean_heart_rate(time_sec, heart_rate)
    if len(hr) == 0:
        return SustainedPeak(math.nan, math.nan, raw_max, window_sec)
    med = held_heart_rate(t, hr, window_sec)
    if not np.isfinite(med).any():
        return SustainedPeak(math.nan, math.nan, raw_max, window_sec)
    i = int(np.nanargmax(med))
    return SustainedPeak(float(med[i]), float(t[i]), raw_max, window_sec)


# ======================
# OBSERVED HRMAX
# ======================


@dataclass
class ObservedHRMax:
    """Highest heart rate held 5 s in the sessions of one sport.

    Attributes:
        sport: Sport code.
        hr_max: The value (bpm).
        date: Date of the session where it was reached.
        session_id: Identifier of that session, when given.
        time_sec: When, in that session (s).
        optical: ``True`` when that session was recorded with an optical
            (wrist) sensor — a less reliable value.

    """

    sport: str
    hr_max: float
    date: str | None = None
    session_id: str | None = None
    time_sec: float = math.nan
    optical: bool = False


def observed_hr_max(
    sessions: Iterable,
    *,
    sport: str | None = None,
    window_sec: float = SUSTAINED_SEC,
    include_optical: bool = True,
) -> dict[str, ObservedHRMax]:
    """Return the highest heart rate held 5 s, per sport, in imported sessions.

    Args:
        sessions: Sessions with second-by-second heart rate. Each one is
            either a :class:`~cardiolab.sensors_tools.garmin.FitRecords`
            (``time_sec``, ``heart_rate``, ``sport``) or a dict with the keys
            ``time_sec``, ``heart_rate`` and optionally ``sport``, ``date``,
            ``session_id``, ``optical``. Objects may carry ``date`` /
            ``session_id`` / ``optical`` attributes too.
        sport: Only this sport (``None`` → every sport, separately).
        window_sec: Duration a value must be held.
        include_optical: ``False`` to ignore sessions recorded with an
            optical sensor.

    Returns:
        ``{sport: ObservedHRMax}`` — sports without any complete 5-s window
        are absent.

    """
    best: dict[str, ObservedHRMax] = {}
    for s in sessions:
        get = (
            s.get
            if isinstance(s, dict)
            else (lambda k, d=None, _s=s: getattr(_s, k, d))
        )
        s_sport = get("sport", "other") or "other"
        if sport is not None and s_sport != sport:
            continue
        optical = bool(get("optical", False))
        if optical and not include_optical:
            continue
        start = get("start", None)
        date = get("date", None) or (
            start.date().isoformat() if start is not None else None
        )
        peak = sustained_peak(get("time_sec"), get("heart_rate"), window_sec=window_sec)
        if not math.isfinite(peak.hr_max):
            continue
        current = best.get(s_sport)
        if current is None or peak.hr_max > current.hr_max:
            best[s_sport] = ObservedHRMax(
                sport=s_sport,
                hr_max=peak.hr_max,
                date=str(date) if date is not None else None,
                session_id=get("session_id", None),
                time_sec=peak.time_sec,
                optical=optical,
            )
    return best


# ======================
# PROFILE UPDATE PROPOSAL
# ======================


@dataclass
class HRMaxProposal:
    """A proposed change of the profile HRmax — never applied by cardiolab.

    Attributes:
        propose: ``True`` when the change should be offered to the athlete.
        reason: Why (or why not), in English.
        current: HRmax of the profile (``None`` if empty).
        current_source: Its source (``None`` if unknown).
        candidate: The new value (rounded bpm).
        source: ``field_test`` or ``observed``.
        changes: What the change would modify — ``zone5_top``,
            ``general_zones`` (old / new bounds), ``lsct_targets`` (old /
            new), ``vo2max_uth`` (old / new, with ``hr_rest``),
            ``reprocess_load`` (``True`` when the load method is
            ``banister``), ``lsct_comparable`` (``False``: later LSCTs no
            longer compare with earlier ones).

    """

    propose: bool
    reason: str
    current: float | None
    current_source: str | None
    candidate: int
    source: str
    changes: dict = field(default_factory=dict)


def _targets(hr_max: float) -> list[int]:
    return [round_bpm(p / 100.0 * hr_max) for p in LSCT_TARGET_PCT]


def propose_hr_max_update(
    current: float | None,
    candidate: float,
    *,
    source: str,
    current_source: str | None = None,
    hr_rest: float | None = None,
    load_method: str | None = None,
) -> HRMaxProposal:
    """Decide whether to offer a new HRmax, and list what it would change.

    Rules:

    * no HRmax in the profile, or one predicted from the age (``tanaka``) →
      offered, whatever the value (a measurement beats a prediction);
    * a higher value → offered;
    * an equal or lower value → not offered: an observed HRmax is a lower
      bound, and a field test that stays below a known value was probably not
      all-out. The athlete can still lower it by hand.

    Args:
        current: HRmax of the profile (``None`` if empty).
        candidate: Measured or observed HRmax (bpm).
        source: ``field_test`` or ``observed``.
        current_source: Source of ``current`` (see :data:`HR_MAX_SOURCES`).
        hr_rest: Resting heart rate, for the VO2max change.
        load_method: Load method of the athlete (``banister`` → sessions to
            reprocess).

    Returns:
        An :class:`HRMaxProposal`.

    Raises:
        ValueError: Unknown source, or ``candidate`` outside 100–230 bpm.

    """
    if source not in ("field_test", "observed"):
        raise ValueError("source must be 'field_test' or 'observed'")
    validate_hr_max_source(current_source)
    if not 100.0 <= candidate <= 230.0:
        raise ValueError(f"HRmax {candidate} bpm is not plausible (100–230).")
    new = round_bpm(candidate)
    if current is None or current_source == "tanaka":
        propose = True
        reason = (
            "no HRmax in the profile"
            if current is None
            else "the profile HRmax is predicted from the age"
        )
    elif new > current:
        propose, reason = True, f"higher than the profile HRmax ({current:g} bpm)"
    else:
        propose = False
        reason = (
            f"not higher than the profile HRmax ({current:g} bpm): an HRmax is never "
            "lowered automatically — change it by hand if the profile value is wrong"
        )
    changes: dict = {}
    if propose:
        changes["zone5_top"] = {"old": current, "new": new}
        changes["general_zones"] = {
            "old": [
                (round_bpm(z.hr_low), round_bpm(z.hr_high))
                for z in five_zones_from_hr_max(current)
            ]
            if current
            else None,
            "new": [
                (round_bpm(z.hr_low), round_bpm(z.hr_high))
                for z in five_zones_from_hr_max(new)
            ],
        }
        changes["lsct_targets"] = {
            "old": _targets(current) if current else None,
            "new": _targets(new),
        }
        changes["lsct_comparable"] = False
        if hr_rest:
            changes["vo2max_uth"] = {
                "old": round(UTH_FACTOR * current / hr_rest, 1) if current else None,
                "new": round(UTH_FACTOR * new / hr_rest, 1),
            }
        changes["reprocess_load"] = load_method == "banister"
    return HRMaxProposal(propose, reason, current, current_source, new, source, changes)
