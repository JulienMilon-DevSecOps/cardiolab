"""Cardiovascular autonomic reflex tests — Ewing battery (heart rate tests).

Three short tests of how the autonomic nervous system changes the heart rate
(Ewing et al. 1985). They complement the daily resting measurement: a
**check-up** once or twice a year, or when a fatigue signal persists.

| Test             | What the person does                                | Result                                   |
| ---------------- | --------------------------------------------------- | ---------------------------------------- |
| Deep breathing   | 6 breaths per minute (5 s in, 5 s out) for 1 min    | Heart rate difference, E/I ratio          |
| Valsalva         | Blow at 40 mmHg for 15 s into a manometer mouthpiece | Valsalva ratio                           |
| 30:15            | Stand up from lying (orthostatic test)              | 30:15 ratio                              |

The blood-pressure tests of the battery (handgrip, orthostatic hypotension)
are out of scope: no blood pressure with the current sensors.

Interpretation — ``normal`` / ``borderline`` / ``abnormal``, reference values
of Ewing et al. (1985) for adults:

| Test                         | Normal  | Borderline  | Abnormal |
| ---------------------------- | ------- | ----------- | -------- |
| Deep breathing (bpm)         | ≥ 15    | 11–14       | ≤ 10     |
| Valsalva ratio               | ≥ 1.21  | 1.11–1.20   | ≤ 1.10   |
| 30:15 ratio                  | ≥ 1.04  | 1.01–1.03   | ≤ 1.00   |

All three responses decrease with age. For deep breathing, when the age is
given, the lower limit is the **age-corrected 5th percentile** of May et al.
(1999), measured in the general population (40–67 years, extrapolated outside
that range): heart rate difference ``(4.39 − 0.033 × age)²`` bpm, E/I ratio
``1 + exp(−1.12 − 0.0198 × age)``. Below it → ``abnormal``; between it and the
adult value of 15 bpm → ``borderline``. No age-corrected limit is applied to
the Valsalva and 30:15 ratios (Ewing values for all ages): in older people
they may be classed lower than they should.

These are **reference values, not a diagnosis**: cardiolab is not a medical
device. A low result is checked again another day, in the same conditions;
if it repeats, it is discussed with a doctor.

Implementation choices (cardiolab):

* deep breathing — breathing cycles found as the troughs of the heart rate
  filtered around 0.1 Hz; per cycle, the shortest RR (inspiration) and the
  longest RR (expiration); results = mean over the complete cycles (Ewing: 6
  cycles; May 1999: 3 consecutive cycles); fewer than 3 cycles →
  ``unreliable``;
* Valsalva — the start of the strain is given (marker); ratio = longest RR
  in the 30 s after the strain / shortest RR during the strain;
* 30:15 — beats counted from the moment of standing: longest RR among beats
  20–40 / shortest RR among beats 5–25. The moment of standing is given, or
  estimated as the start of the heart rate rise of the orthostatic test.

References:
    Ewing, D. J., Martyn, C. N., Young, R. J., & Clarke, B. F. (1985). The
    value of cardiovascular autonomic function tests: 10 years experience in
    diabetes. Diabetes Care, 8(5), 491–498.

    May, O., Arildsen, H., & Møller, M. (1999). Parasympathetic function
    during deep breathing in the general population: relation to coronary
    risk factors and normal range. Journal of Internal Medicine, 245(3),
    287–294.

    Shields, R. W. (2009). Heart rate variability with deep breathing as a
    clinical test of cardiovagal function. Cleveland Clinic Journal of
    Medicine, 76(Suppl 2), S37–S40.

"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

from cardiolab.protocols.orthostatic import OrthostaticResult, detect_phases
from cardiolab.signals.rr import RRSeries

# ── Reference values ─────────────────────────────────────────────────────────

INTERPRETATIONS: tuple[str, ...] = ("normal", "borderline", "abnormal")
"""Interpretation labels."""

EWING_LIMITS: dict[str, tuple[float, float]] = {
    "deep_breathing": (15.0, 10.0),
    "valsalva": (1.21, 1.10),
    "ratio_30_15": (1.04, 1.00),
}
"""``(normal from, abnormal up to)`` of each test — Ewing et al. (1985)."""

REFERENCE_EWING = "ewing_1985"
REFERENCE_MAY = "may_1999"

BREATHING_CYCLE_SEC = 10.0
"""Paced breathing: 6 cycles per minute."""

MIN_CYCLES = 3
"""Minimum complete breathing cycles for a reliable deep breathing result."""

VALSALVA_STRAIN_SEC = 15.0
VALSALVA_RECOVERY_SEC = 30.0

SHORTEST_BEATS_30_15 = (5, 25)
LONGEST_BEATS_30_15 = (20, 40)


def classify(value: float, test: str, lower_limit: float | None = None) -> str:
    """Classify a result as ``normal`` / ``borderline`` / ``abnormal``.

    Args:
        value: The result (bpm for deep breathing, a ratio otherwise).
        test: ``"deep_breathing"``, ``"valsalva"`` or ``"ratio_30_15"``.
        lower_limit: Age-corrected lower limit. When given, a value below it is
            ``abnormal`` and a value between it and the Ewing normal value is
            ``borderline``.

    Returns:
        The interpretation, or ``""`` when ``value`` is not finite.

    Raises:
        ValueError: If ``test`` is unknown.

    """
    if test not in EWING_LIMITS:
        raise ValueError(
            f"Unknown test {test!r}; expected one of {list(EWING_LIMITS)}."
        )
    if not math.isfinite(value):
        return ""
    normal_from, abnormal_to = EWING_LIMITS[test]
    if lower_limit is not None:
        if value < lower_limit:
            return "abnormal"
        return "normal" if value >= normal_from else "borderline"
    if value >= normal_from:
        return "normal"
    return "abnormal" if value <= abnormal_to else "borderline"


def deep_breathing_limits(age: float) -> tuple[float, float]:
    """Age-corrected 5th percentiles of deep breathing (May et al. 1999).

    Args:
        age: Age in years (study range 40–67; extrapolated outside).

    Returns:
        ``(heart rate difference in bpm, E/I ratio)`` — values below are
        abnormal.

    Raises:
        ValueError: If ``age`` is not between 10 and 100.

    """
    if not 10 <= age <= 100:
        raise ValueError(f"age must be between 10 and 100 years, got {age}.")
    return (4.39 - 0.033 * age) ** 2, 1.0 + math.exp(-1.12 - 0.0198 * age)


def _intervals(rr) -> np.ndarray:
    values = rr.intervals if isinstance(rr, RRSeries) else rr
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("At least 2 RR intervals (ms) are required.")
    if np.any(~np.isfinite(values)) or np.any(values <= 0):
        raise ValueError("RR intervals must be positive finite values (ms).")
    return values


# ======================
# DEEP BREATHING
# ======================


@dataclass
class BreathingCycle:
    """One breathing cycle of the deep breathing test.

    Attributes:
        start_sec: Start of the cycle (trough of the filtered heart rate).
        end_sec: End of the cycle.
        max_rr: Longest RR of the cycle (ms) — expiration.
        min_rr: Shortest RR of the cycle (ms) — inspiration.

    """

    start_sec: float
    end_sec: float
    max_rr: float
    min_rr: float

    @property
    def hr_difference(self) -> float:
        """Highest minus lowest heart rate of the cycle (bpm)."""
        return 60000.0 / self.min_rr - 60000.0 / self.max_rr

    @property
    def ei_ratio(self) -> float:
        """Longest / shortest RR (expiration / inspiration)."""
        return self.max_rr / self.min_rr


@dataclass
class DeepBreathingResult:
    """Result of the deep breathing test.

    Attributes:
        hr_difference: Mean of the heart rate differences of the cycles (bpm).
        ei_ratio: Mean of the E/I ratios of the cycles.
        n_cycles: Complete breathing cycles used.
        breathing_rate: Breaths per minute (6 when paced as asked).
        interpretation: ``normal`` / ``borderline`` / ``abnormal`` on
            ``hr_difference``.
        reference: ``ewing_1985`` (adult values) or ``may_1999`` (age).
        age: Age used for the limits, ``None`` without.
        hr_difference_limit: Lower limit used for ``hr_difference`` (bpm).
        ei_ratio_limit: Age-corrected lower limit of the E/I ratio (``nan``
            without age).
        status: ``ok`` or ``unreliable`` (too few cycles).
        cycles: The cycles (not stored in the database).
        warnings: Notes on how the test was done.

    """

    hr_difference: float
    ei_ratio: float
    n_cycles: int
    breathing_rate: float
    interpretation: str
    reference: str = REFERENCE_EWING
    age: float | None = None
    hr_difference_limit: float = EWING_LIMITS["deep_breathing"][1]
    ei_ratio_limit: float = math.nan
    status: str = "ok"
    cycles: list[BreathingCycle] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _cycle_troughs(t: np.ndarray, hr: np.ndarray, cycle_sec: float) -> np.ndarray:
    """Return the troughs of the heart rate filtered around the breathing rate (s)."""
    fs = 4.0
    grid = np.arange(t[0], t[-1], 1.0 / fs)
    if len(grid) < 4 * fs * cycle_sec / 2:
        return np.array([])
    hr_grid = np.interp(grid, t, hr)
    f0 = 1.0 / cycle_sec
    b, a = butter(2, [f0 / 2, f0 * 2], btype="bandpass", fs=fs)
    if len(grid) <= 3 * max(len(a), len(b)):
        return np.array([])
    smooth = filtfilt(b, a, hr_grid - hr_grid.mean())
    troughs, _ = find_peaks(-smooth, distance=int(0.6 * cycle_sec * fs))
    return grid[troughs]


def deep_breathing_test(
    rr,
    *,
    age: float | None = None,
    cycle_sec: float = BREATHING_CYCLE_SEC,
) -> DeepBreathingResult:
    """Analyse a deep breathing test (6 breaths per minute, about 1 minute).

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` or RR intervals in ms,
            starting with the first paced breath.
        age: Age in years — age-corrected limits of May et al. (1999). Without
            it, the adult values of Ewing et al. (1985).
        cycle_sec: Expected breathing cycle (10 s = 6 breaths per minute).

    Returns:
        A :class:`DeepBreathingResult`. With fewer than 3 complete cycles,
        ``status = "unreliable"`` and a warning.

    Raises:
        ValueError: If the RR intervals are invalid or the age is out of range.

    """
    intervals = _intervals(rr)
    t = np.cumsum(intervals) / 1000.0
    hr = 60000.0 / intervals
    troughs = _cycle_troughs(t, hr, cycle_sec)

    cycles = []
    for start, end in zip(troughs[:-1], troughs[1:], strict=False):
        inside = (t >= start) & (t < end)
        if inside.sum() >= 3:
            cycles.append(
                BreathingCycle(
                    float(start),
                    float(end),
                    float(intervals[inside].max()),
                    float(intervals[inside].min()),
                )
            )

    notes: list[str] = []
    status = "ok"
    if len(cycles) < MIN_CYCLES:
        status = "unreliable"
        notes.append(
            f"Only {len(cycles)} complete breathing cycle(s) found (at least "
            f"{MIN_CYCLES} needed): breathe at 6 breaths per minute for 1 minute."
        )
    hr_difference = (
        float(np.mean([c.hr_difference for c in cycles])) if cycles else math.nan
    )
    ei_ratio = float(np.mean([c.ei_ratio for c in cycles])) if cycles else math.nan
    rate = (
        60.0 / float(np.mean([c.end_sec - c.start_sec for c in cycles]))
        if cycles
        else math.nan
    )
    if cycles and not 5.0 <= rate <= 7.0:
        notes.append(
            f"Breathing rate {rate:.1f} per minute instead of 6: follow the 5 s in, "
            "5 s out guide."
        )

    if age is not None:
        diff_limit, ratio_limit = deep_breathing_limits(age)
        reference = REFERENCE_MAY
        if not 40 <= age <= 67:
            notes.append(
                f"Age {age:g}: limits of May et al. (1999) extrapolated outside "
                "40–67 years."
            )
    else:
        diff_limit, ratio_limit = EWING_LIMITS["deep_breathing"][1], math.nan
        reference = REFERENCE_EWING
    interpretation = classify(
        hr_difference, "deep_breathing", diff_limit if age is not None else None
    )
    for note in notes:
        warnings.warn(note, stacklevel=2)
    return DeepBreathingResult(
        hr_difference=hr_difference,
        ei_ratio=ei_ratio,
        n_cycles=len(cycles),
        breathing_rate=rate,
        interpretation=interpretation,
        reference=reference,
        age=age,
        hr_difference_limit=diff_limit,
        ei_ratio_limit=ratio_limit,
        status=status,
        cycles=cycles,
        warnings=notes,
    )


# ======================
# VALSALVA
# ======================


@dataclass
class ValsalvaResult:
    """Result of the Valsalva manoeuvre.

    Attributes:
        ratio: Longest RR after the strain / shortest RR during it.
        max_hr: Highest heart rate during the strain (bpm).
        min_hr: Lowest heart rate in the 30 s after it (bpm).
        baseline_hr: Mean heart rate in the 30 s before the strain (``nan``
            if the recording starts later).
        strain_sec: Duration of the strain (s).
        interpretation: ``normal`` / ``borderline`` / ``abnormal`` (Ewing).
        status: ``ok`` or ``unreliable``.
        warnings: Notes on how the test was done.

    """

    ratio: float
    max_hr: float
    min_hr: float
    baseline_hr: float
    strain_sec: float
    interpretation: str
    status: str = "ok"
    warnings: list[str] = field(default_factory=list)


def valsalva_ratio(
    rr,
    strain_start_sec: float,
    strain_end_sec: float | None = None,
    *,
    recovery_sec: float = VALSALVA_RECOVERY_SEC,
) -> ValsalvaResult:
    """Analyse a Valsalva manoeuvre (blow at 40 mmHg for 15 s).

    Args:
        rr: :class:`~cardiolab.signals.rr.RRSeries` or RR intervals in ms.
        strain_start_sec: Start of the strain, in seconds from the start of
            the recording (marker).
        strain_end_sec: End of the strain. Defaults to start + 15 s.
        recovery_sec: Window after the strain for the longest RR.

    Returns:
        A :class:`ValsalvaResult`. ``unreliable`` when the recording does not
        cover the strain and at least 20 s after it.

    Raises:
        ValueError: If the RR intervals are invalid, the strain lasts less
            than 5 s, or the recording has no beat during the strain.

    """
    intervals = _intervals(rr)
    t = np.cumsum(intervals) / 1000.0
    end = (
        strain_start_sec + VALSALVA_STRAIN_SEC
        if strain_end_sec is None
        else strain_end_sec
    )
    strain = end - strain_start_sec
    if strain < 5.0:
        raise ValueError(f"The strain must last at least 5 s, got {strain:g} s.")
    during = (t >= strain_start_sec) & (t <= end)
    after = (t > end) & (t <= end + recovery_sec)
    if not during.any():
        raise ValueError("No beat during the strain: check strain_start_sec.")

    notes: list[str] = []
    status = "ok"
    if t[-1] < end + 20.0 or not after.any():
        status = "unreliable"
        notes.append("The recording stops less than 20 s after the strain.")
    if not 10.0 <= strain <= 20.0:
        notes.append(f"Strain of {strain:g} s: the protocol asks for 15 s.")

    shortest = float(intervals[during].min())
    longest = float(intervals[after].max()) if after.any() else math.nan
    before = (t >= strain_start_sec - 30.0) & (t < strain_start_sec)
    baseline = float(np.mean(60000.0 / intervals[before])) if before.any() else math.nan
    max_hr = 60000.0 / shortest
    if math.isfinite(baseline) and max_hr - baseline < 5.0:
        notes.append(
            "The heart rate barely rose during the strain: the blowing was "
            "probably too weak (40 mmHg on the manometer)."
        )
    ratio = longest / shortest
    for note in notes:
        warnings.warn(note, stacklevel=2)
    return ValsalvaResult(
        ratio=ratio,
        max_hr=max_hr,
        min_hr=60000.0 / longest,
        baseline_hr=baseline,
        strain_sec=strain,
        interpretation=classify(ratio, "valsalva"),
        status=status,
        warnings=notes,
    )


# ======================
# 30:15 RATIO
# ======================


@dataclass
class Ratio3015Result:
    """Result of the 30:15 ratio.

    Attributes:
        ratio: Longest RR among beats 20–40 / shortest among beats 5–25 after
            standing.
        stand_sec: Moment of standing (s from the start of the recording).
        stand_estimated: ``True`` when ``stand_sec`` was estimated from the
            heart rate rise.
        shortest_beat: Beat number (after standing) of the shortest RR.
        longest_beat: Beat number of the longest RR.
        interpretation: ``normal`` / ``borderline`` / ``abnormal`` (Ewing).

    """

    ratio: float
    stand_sec: float
    stand_estimated: bool
    shortest_beat: int
    longest_beat: int
    interpretation: str


def _full_rr(source) -> tuple[np.ndarray, OrthostaticResult | None]:
    if isinstance(source, OrthostaticResult):
        phases = source.phases
        parts = [phases.supine.rr, phases.transition.rr, phases.standing.rr]
        return np.concatenate([p.intervals for p in parts]), source
    return _intervals(source), None


def _estimate_stand(intervals: np.ndarray, result: OrthostaticResult | None) -> int:
    """Index of the first beat of the heart rate rise when standing up."""
    t = np.cumsum(intervals) / 1000.0
    hr = 60000.0 / intervals
    phases = detect_phases(RRSeries(intervals)) if result is None else result.phases
    onset = phases.transition.start_sec
    supine = t < max(onset - 30.0, t[0] + 10.0)
    baseline = float(np.median(hr[supine])) if supine.sum() >= 5 else float(hr[0])
    # The trailing 30-s mean of detect_phases lags the real rise: search before it
    window = np.where((t >= onset - 40.0) & (t <= onset + 20.0))[0]
    if len(window) < 3:
        raise ValueError("Cannot locate the moment of standing: give stand_sec.")
    smooth = np.convolve(hr, np.ones(3) / 3, mode="same")
    peak = int(window[np.argmax(smooth[window])])
    rise = baseline + 0.25 * (smooth[peak] - baseline)
    i = peak
    while i > 0 and smooth[i - 1] > rise:
        i -= 1
    return i


def ratio_30_15(source, *, stand_sec: float | None = None) -> Ratio3015Result:
    """Compute the 30:15 ratio after standing up.

    Args:
        source: :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
            (its three phases give the whole recording) or the RR intervals of
            a lying → standing recording.
        stand_sec: Moment of standing, in seconds from the start of the
            recording. Defaults to an estimate: the start of the heart rate
            rise.

    Returns:
        A :class:`Ratio3015Result`.

    Raises:
        ValueError: If fewer than 40 beats follow the moment of standing, or
            the moment of standing cannot be located.

    """
    intervals, result = _full_rr(source)
    t = np.cumsum(intervals) / 1000.0
    if stand_sec is None:
        stand = _estimate_stand(intervals, result)
        estimated = True
    else:
        stand = int(np.searchsorted(t, stand_sec))
        estimated = False
    lo_a, hi_a = SHORTEST_BEATS_30_15
    lo_b, hi_b = LONGEST_BEATS_30_15
    if stand + hi_b >= len(intervals):
        raise ValueError("At least 40 beats are needed after standing up.")
    short_idx = (
        stand + lo_a + int(np.argmin(intervals[stand + lo_a : stand + hi_a + 1]))
    )
    long_idx = stand + lo_b + int(np.argmax(intervals[stand + lo_b : stand + hi_b + 1]))
    ratio = float(intervals[long_idx] / intervals[short_idx])
    return Ratio3015Result(
        ratio=ratio,
        stand_sec=float(t[stand - 1]) if stand > 0 else 0.0,
        stand_estimated=estimated,
        shortest_beat=short_idx - stand,
        longest_beat=long_idx - stand,
        interpretation=classify(ratio, "ratio_30_15"),
    )


# ======================
# BATTERY (storage)
# ======================


@dataclass
class AutonomicTestsResult:
    """The tests of one day — any of them may be missing.

    Attributes:
        date: ISO date.
        deep_breathing: Deep breathing result, or ``None``.
        valsalva: Valsalva result, or ``None``.
        ratio_30_15: 30:15 result, or ``None``.

    """

    date: str
    deep_breathing: DeepBreathingResult | None = None
    valsalva: ValsalvaResult | None = None
    ratio_30_15: Ratio3015Result | None = None

    def to_dict(self) -> dict:
        """Flat dict — the columns of the ``hrv_autonomic_tests`` table."""
        db, va, r = self.deep_breathing, self.valsalva, self.ratio_30_15
        return {
            "date": self.date,
            "age": db.age if db else None,
            "db_hr_difference": db.hr_difference if db else None,
            "db_ei_ratio": db.ei_ratio if db else None,
            "db_n_cycles": db.n_cycles if db else None,
            "db_breathing_rate": db.breathing_rate if db else None,
            "db_interpretation": db.interpretation if db else None,
            "db_reference": db.reference if db else None,
            "db_status": db.status if db else None,
            "valsalva_ratio": va.ratio if va else None,
            "valsalva_max_hr": va.max_hr if va else None,
            "valsalva_min_hr": va.min_hr if va else None,
            "valsalva_strain_sec": va.strain_sec if va else None,
            "valsalva_interpretation": va.interpretation if va else None,
            "valsalva_status": va.status if va else None,
            "ratio_30_15": r.ratio if r else None,
            "ratio_30_15_stand_sec": r.stand_sec if r else None,
            "ratio_30_15_stand_estimated": r.stand_estimated if r else None,
            "ratio_30_15_interpretation": r.interpretation if r else None,
        }
