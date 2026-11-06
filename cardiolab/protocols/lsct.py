"""Lamberts and Lambert Submaximal Cycle Test (LSCT).

A short submaximal cycling test (17.5 min) to follow fitness and fatigue week
after week without an all-out effort. The heart rate is imposed, the power is
measured:

| Stage    | Duration | Target                         |
| -------- | -------- | ------------------------------ |
| 1        | 6 min    | 60 % of HRmax                  |
| 2        | 6 min    | 80 % of HRmax                  |
| 3        | 3 min    | 90 % of HRmax                  |
| Recovery | 90 s     | stop pedalling, sit upright    |

Recorded per stage: mean power and perceived exertion (RPE). After stage 3,
the heart rate recovery over 60 s (HRR60). Power in stages 2 and 3 is the
most reliable variable (ICC 0.85–1.00, typical error 1.3–4.4 %) and the best
predictor of performance (r = 0.80–0.94 with the 40-km time trial); HRR is
less informative (r = 0.55–0.68) (Lamberts et al. 2011).

Reading changes (cardiolab heuristics, after the studies below):

* more power at the same heart rate, same RPE → **improving**;
* less power → **fatigue possible** (power and RPE responded to a fatiguing
  training period and recovered after it — training-camp study);
* more power **with** higher RPE, or stage 3 target heart rate not reached →
  **possible overreaching** (Decroix et al. 2017, n = 6).

Compare an athlete with their own previous tests only, with the **same HRmax**
for the targets, the same bike and trainer, and at the same time of day.

Implementation choices (cardiolab):

* the test starts at ``start_sec`` (default: the start of the file); stages
  follow back to back;
* mean power and mean heart rate over the whole stage; ``hr_end`` = mean
  heart rate over the stage's last minute; the target is reached when
  ``hr_end`` ≥ target − 2 bpm (practical tolerance ±1–2 bpm);
* a stage held more than 5 bpm away from its target (above it, or below it
  for stages 1–2) is flagged ``stage<n>_off_target``: not ridden as
  prescribed, not comparable;
* HRR60 = heart rate at the end of stage 3 minus 60 s later, each a 5-s
  median (as in :mod:`cardiolab.protocols.hrr`);
* a change counts above 5 % of power (above the largest typical error,
  4.4 %) or 1 point of RPE.

References:
    Lamberts, R. P., Swart, J., Noakes, T. D., & Lambert, M. I. (2011). A
    novel submaximal cycle test to monitor fatigue and predict cycling
    performance. British Journal of Sports Medicine, 45(10), 797–804.

    Decroix, L., Lamberts, R. P., & Meeusen, R. (2017). Can the Lamberts and
    Lambert Submaximal Cycle Test reflect overreaching in professional
    cyclists? International Journal of Sports Physiology and Performance.
    PubMed 28422523.

"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

from cardiolab.signals.rr import PhysiologicalWarning

STAGES: tuple[tuple[float, float], ...] = ((60.0, 360.0), (80.0, 360.0), (90.0, 180.0))
"""``(target % of HRmax, duration s)`` of the three stages."""

RECOVERY_SEC = 90.0
"""Seated recovery after stage 3 (s)."""

HRR_SEC = 60.0
"""Heart rate recovery delay (s)."""

SMOOTH_SEC = 5.0
"""Window of the heart rate medians used for HRR60 (s)."""

TARGET_TOLERANCE_BPM = 2.0
"""A stage target is reached when the last-minute heart rate is within this margin."""

OFF_TARGET_BPM = 5.0
"""A stage held more than this away from its target was not ridden as prescribed."""

MEANINGFUL_POWER_PCT = 5.0
"""Power change counted as real (%), above the largest typical error (4.4 %)."""

MEANINGFUL_RPE = 1.0
"""RPE change counted as real (points)."""


@dataclass
class LSCTStage:
    """One stage of the test.

    Attributes:
        stage: 1, 2 or 3.
        target_pct: Target heart rate as % of HRmax.
        target_hr: Target heart rate (bpm).
        mean_power: Mean power over the stage (W).
        mean_hr: Mean heart rate over the stage (bpm).
        hr_end: Mean heart rate over the stage's last minute (bpm).
        target_reached: ``hr_end`` ≥ target − 2 bpm.
        rpe: Perceived exertion entered by the athlete, or ``None``.

    """

    stage: int
    target_pct: float
    target_hr: float
    mean_power: float
    mean_hr: float
    hr_end: float
    target_reached: bool
    rpe: float | None = None


@dataclass
class LSCTResult:
    """Results of a Lamberts submaximal cycle test.

    Attributes:
        stages: The three stages.
        hrr_60: Heart rate drop 60 s after stage 3 (bpm), ``nan`` when the
            recovery was not recorded.
        hr_max: HRmax used for the targets (bpm).
        start_sec: Start of the test in the recording (s).
        date: Date of the test, when given.

    """

    stages: list[LSCTStage]
    hrr_60: float
    hr_max: float
    start_sec: float = 0.0
    date: str | None = None
    warnings: list[str] = field(default_factory=list)

    def stage(self, number: int) -> LSCTStage:
        """Return stage ``number`` (1, 2 or 3)."""
        return self.stages[number - 1]

    def to_dict(self) -> dict:
        """Return a flat, JSON-ready dict — also the storage columns."""
        out: dict = {
            "date": self.date,
            "hr_max": self.hr_max,
            "start_sec": self.start_sec,
            "hrr_60": self.hrr_60,
        }
        for s in self.stages:
            p = f"stage{s.stage}_"
            out[p + "power"] = s.mean_power
            out[p + "hr"] = s.mean_hr
            out[p + "hr_end"] = s.hr_end
            out[p + "target_reached"] = s.target_reached
            out[p + "rpe"] = s.rpe
        return out


@dataclass
class LSCTComparison:
    """Change of a test against a reference (previous test or mean of several).

    Attributes:
        power_change_pct: Change of the mean power of stages 2 and 3 (%).
        rpe_change: Change of the mean RPE of stages 2 and 3 (points), or
            ``None`` without RPE on both sides.
        hrr_change: Change of HRR60 (bpm), ``nan`` if missing.
        target_reached: Stage 3 target reached in the current test.
        interpretation: ``"improving"``, ``"fatigue_possible"``,
            ``"overreaching_possible"`` or ``"stable"``.

    """

    power_change_pct: float
    rpe_change: float | None
    hrr_change: float
    target_reached: bool
    interpretation: str


def lsct(
    time_sec: np.ndarray,
    heart_rate: np.ndarray,
    power: np.ndarray,
    hr_max: float,
    *,
    start_sec: float = 0.0,
    rpe: tuple[float | None, float | None, float | None] | None = None,
    date: str | None = None,
) -> LSCTResult:
    """Analyse a Lamberts submaximal cycle test.

    Args:
        time_sec: Sample times (s), e.g. ``FitRecords.time_sec`` (1 Hz).
        heart_rate: Heart rate at each time (bpm, ``nan`` when missing).
        power: Power at each time (W).
        hr_max: HRmax used for the targets (bpm) — keep the same one from test
            to test.
        start_sec: Start of stage 1 in the recording (s).
        rpe: Perceived exertion of stages 1–3, entered by the athlete (same
            scale every time); ``None`` when not given.
        date: Date of the test (ISO), stored with the result.

    Returns:
        ``LSCTResult`` with the three stages and HRR60.

    Raises:
        ValueError: If the arrays differ in length, ``hr_max`` is not
            positive, the recording ends before the end of stage 3, or a stage
            has no heart rate or no power.

    Warns:
        PhysiologicalWarning: When the recovery is missing (HRR60 ``nan``) or
            the stage 3 target was not reached.

    """
    t = np.asarray(time_sec, dtype=float)
    hr = np.asarray(heart_rate, dtype=float)
    pw = np.asarray(power, dtype=float)
    if not (len(t) == len(hr) == len(pw)):
        raise ValueError("time_sec, heart_rate and power must have the same length")
    if not hr_max > 0:
        raise ValueError(f"hr_max must be positive, got {hr_max}")
    end_stage3 = start_sec + sum(d for _, d in STAGES)
    if len(t) == 0 or t[-1] < end_stage3 - 1.0:
        raise ValueError(
            f"Recording ends before the end of stage 3 ({end_stage3:.0f} s from the "
            "start of the file): check start_sec."
        )
    rpes = tuple(rpe) if rpe is not None else (None, None, None)

    stages: list[LSCTStage] = []
    t0 = start_sec
    for i, (pct, duration) in enumerate(STAGES, start=1):
        t1 = t0 + duration
        in_stage = (t >= t0) & (t < t1)
        last_min = (t >= t1 - 60.0) & (t < t1)
        if not np.any(in_stage & np.isfinite(hr)) or not np.any(
            in_stage & np.isfinite(pw)
        ):
            raise ValueError(f"Stage {i} has no heart rate or no power")
        target = pct / 100.0 * hr_max
        hr_end = float(np.nanmean(hr[last_min]))
        stages.append(
            LSCTStage(
                stage=i,
                target_pct=pct,
                target_hr=target,
                mean_power=float(np.nanmean(pw[in_stage])),
                mean_hr=float(np.nanmean(hr[in_stage])),
                hr_end=hr_end,
                target_reached=bool(hr_end >= target - TARGET_TOLERANCE_BPM),
                rpe=None if rpes[i - 1] is None else float(rpes[i - 1]),
            )
        )
        t0 = t1

    notes: list[str] = []
    hr_stop = _median_near(t, hr, end_stage3 - SMOOTH_SEC / 2.0)
    hr_after = _median_near(t, hr, end_stage3 + HRR_SEC)
    hrr_60 = hr_stop - hr_after
    if not np.isfinite(hrr_60):
        notes.append("recovery_missing")
        warnings.warn(
            "No heart rate 60 s after stage 3: HRR60 not computed. Keep recording "
            "during the 90-s seated recovery.",
            PhysiologicalWarning,
            stacklevel=2,
        )
    for s in stages:
        too_high = s.hr_end > s.target_hr + OFF_TARGET_BPM
        too_low = s.stage < 3 and s.hr_end < s.target_hr - OFF_TARGET_BPM
        if too_high or too_low:
            notes.append(f"stage{s.stage}_off_target")
            warnings.warn(
                f"Stage {s.stage} held at {s.hr_end:.0f} bpm instead of "
                f"{s.target_hr:.0f} bpm: the test is not comparable with the "
                "others. Check start_sec and the HRmax.",
                PhysiologicalWarning,
                stacklevel=2,
            )
    if not stages[2].target_reached:
        notes.append("stage3_target_not_reached")
        warnings.warn(
            f"Stage 3 target ({stages[2].target_hr:.0f} bpm) not reached "
            f"({stages[2].hr_end:.0f} bpm over the last minute) — a sign of fatigue "
            "if it is usually reached.",
            PhysiologicalWarning,
            stacklevel=2,
        )

    return LSCTResult(
        stages=stages,
        hrr_60=float(hrr_60),
        hr_max=float(hr_max),
        start_sec=float(start_sec),
        date=date,
        warnings=notes,
    )


def lsct_from_records(
    records,
    hr_max: float,
    *,
    start_sec: float = 0.0,
    rpe: tuple[float | None, float | None, float | None] | None = None,
    date: str | None = None,
) -> LSCTResult:
    """Analyse an LSCT from a FIT file read by :func:`~cardiolab.sensors_tools.parse_fit_records`.

    Args:
        records: ``FitRecords`` with heart rate and power.
        hr_max: HRmax used for the targets (bpm).
        start_sec: Start of stage 1 in the file (s).
        rpe: Perceived exertion of stages 1–3.
        date: Date of the test; defaults to the date of the first record.

    Returns:
        ``LSCTResult``.

    """
    return lsct(
        records.time_sec,
        records.heart_rate,
        records.power,
        hr_max,
        start_sec=start_sec,
        rpe=rpe,
        date=date or records.start.date().isoformat(),
    )


def compare_lsct(
    current: LSCTResult, reference: LSCTResult | list[LSCTResult]
) -> LSCTComparison:
    """Compare a test with a previous one, or with the mean of several.

    Args:
        current: The latest test.
        reference: A previous test, or a list of previous tests (their means
            are used — e.g. the last 3–4 weeks).

    Returns:
        ``LSCTComparison`` with the changes and their interpretation (see the
        module docstring).

    Raises:
        ValueError: If ``reference`` is an empty list.

    """
    refs = reference if isinstance(reference, list) else [reference]
    if not refs:
        raise ValueError("reference must contain at least one test")

    ref_power = float(np.mean([_power_23(r) for r in refs]))
    power_change = 100.0 * (_power_23(current) - ref_power) / ref_power

    cur_rpe = _rpe_23(current)
    ref_rpes = [x for x in (_rpe_23(r) for r in refs) if x is not None]
    rpe_change = (
        cur_rpe - float(np.mean(ref_rpes)) if cur_rpe is not None and ref_rpes else None
    )
    ref_hrr = [r.hrr_60 for r in refs if np.isfinite(r.hrr_60)]
    hrr_change = current.hrr_60 - float(np.mean(ref_hrr)) if ref_hrr else float("nan")
    reached = current.stage(3).target_reached

    power_up = power_change >= MEANINGFUL_POWER_PCT
    power_down = power_change <= -MEANINGFUL_POWER_PCT
    rpe_up = rpe_change is not None and rpe_change >= MEANINGFUL_RPE
    if power_down:
        interpretation = "fatigue_possible"
    elif not reached or (power_up and rpe_up):
        interpretation = "overreaching_possible"
    elif power_up:
        interpretation = "improving"
    else:
        interpretation = "stable"

    return LSCTComparison(
        power_change_pct=power_change,
        rpe_change=rpe_change,
        hrr_change=hrr_change,
        target_reached=reached,
        interpretation=interpretation,
    )


# ======================
# INTERNAL HELPERS
# ======================


def _median_near(t: np.ndarray, hr: np.ndarray, centre: float) -> float:
    """Median heart rate within ±2.5 s of ``centre``, ``nan`` without samples."""
    half = SMOOTH_SEC / 2.0
    window = hr[(t >= centre - half) & (t <= centre + half)]
    window = window[np.isfinite(window)]
    return float(np.median(window)) if len(window) else float("nan")


def _power_23(result: LSCTResult) -> float:
    """Mean power of stages 2 and 3 (W)."""
    return (result.stage(2).mean_power + result.stage(3).mean_power) / 2.0


def _rpe_23(result: LSCTResult) -> float | None:
    """Mean RPE of stages 2 and 3, or ``None`` if either is missing."""
    a, b = result.stage(2).rpe, result.stage(3).rpe
    return None if a is None or b is None else (a + b) / 2.0
