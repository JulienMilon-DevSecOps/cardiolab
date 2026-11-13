"""HRmax field test — Olympiatoppen protocol.

A **maximal** test (unlike the LSCT): the last repetition goes to exhaustion.
Protocol (Olympiatoppen intensity scale, 2024):

| Phase            | Duration                                                    |
| ---------------- | ----------------------------------------------------------- |
| Warm-up          | 15 min, easy to moderate                                    |
| Repetitions 1–2  | 3 min each, harder each time, uphill (or treadmill 6–10 %)  |
| Between          | 2 min easy jog                                              |
| Repetition 3     | 3 min, +0.5 km/h every minute, to exhaustion                |

Result: the highest heart rate **held 5 s** (reached for a whole 5-s window
— :func:`cardiolab.analytics.hr_max.sustained_peak`); a one-second spike is
an artefact, not an HRmax. HRmax is usually 5–10 bpm lower on the bike than
running: the sport is stored with the result.

Checks (cardiolab):

* **chest strap** required — optical sensors lose the beat at high intensity
  (Gillinov et al. 2017): ``sensor="optical"`` → ``invalid``;
* **final effort**: the held heart rate stays ≥ 90 % of the peak for at least
  60 s before it — a short burst does not reach HRmax;
* **plateau**: the held heart rate stays within 3 bpm of the peak for at
  least 20 s around it — a heart rate still rising steeply when the effort
  stops has not reached its maximum;
* an isolated raw spike more than 5 bpm above the held peak is reported (not
  retained).

Status ``valid`` (both criteria met), ``doubtful`` (value reported, not to be
proposed for the profile) or ``invalid``. A new HRmax is only ever proposed
(:func:`cardiolab.analytics.hr_max.propose_hr_max_update`).

Safety: an all-out effort. Medical advice first after 35–40 years without
regular hard exercise, with a heart condition, high blood pressure,
diabetes, or symptoms on exertion (ACSM pre-participation screening, Riebe et
al. 2015). Not a medical device.

References:
    Olympiatoppen (2024). Olympiatoppen's intensity scale, version 2.

    Riebe, D., et al. (2015). Updating ACSM's recommendations for exercise
    preparticipation health screening. Medicine & Science in Sports &
    Exercise, 47(11), 2473–2479.

    Robergs, R. A., & Landwehr, R. (2002). The surprising history of the
    "HRmax = 220 − age" equation. Journal of Exercise Physiology Online,
    5(2), 1–10.

"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field

import numpy as np

from cardiolab.analytics.hr_max import (
    SUSTAINED_SEC,
    clean_heart_rate,
    held_heart_rate,
    round_bpm,
    sustained_peak,
)
from cardiolab.sports import validate_sport

STATUSES: tuple[str, ...] = ("valid", "doubtful", "invalid")
SENSORS: tuple[str, ...] = ("chest_strap", "optical")

FINAL_EFFORT_PCT = 90.0
"""Held heart rate counted as final effort (% of the peak)."""

MIN_FINAL_EFFORT_SEC = 60.0
PLATEAU_SEC = 20.0
PLATEAU_BPM = 3.0


@dataclass
class HRMaxTestResult:
    """Result of an HRmax field test.

    Attributes:
        hr_max: Highest heart rate held 5 s (bpm), rounded.
        sport: Sport code.
        date: ISO date.
        peak_time_sec: When the peak was reached (s from the start).
        raw_max: Highest single sample (bpm).
        final_effort_sec: Time held ≥ 90 % of the peak just before it (s).
        plateau_reached: Held heart rate within 3 bpm of the peak for at
            least 20 s around it.
        sensor: ``chest_strap``, ``optical`` or ``None`` (not given).
        status: ``valid``, ``doubtful`` or ``invalid``.
        warnings: Notes on the test.

    """

    hr_max: float
    sport: str
    date: str | None
    peak_time_sec: float
    raw_max: float
    final_effort_sec: float
    plateau_reached: bool
    sensor: str | None = None
    status: str = "valid"
    warnings: list[str] = field(default_factory=list)

    @property
    def can_update_profile(self) -> bool:
        """``True`` when the value may be proposed for the profile."""
        return self.status == "valid"

    def to_dict(self) -> dict:
        """Flat dict — the columns of the ``hrv_hr_max_tests`` table."""
        return {
            "date": self.date,
            "sport": self.sport,
            "hr_max": self.hr_max,
            "peak_time_sec": self.peak_time_sec,
            "raw_max": self.raw_max,
            "final_effort_sec": self.final_effort_sec,
            "plateau_reached": self.plateau_reached,
            "sensor": self.sensor,
            "status": self.status,
        }


def hr_max_test(
    time_sec=None,
    heart_rate=None,
    *,
    records=None,
    sport: str | None = None,
    sensor: str | None = None,
    date: str | None = None,
) -> HRMaxTestResult:
    """Analyse an HRmax field test recorded second by second.

    Args:
        time_sec: Time of each sample (s) — or give ``records``.
        heart_rate: Heart rate (bpm).
        records: A :class:`~cardiolab.sensors_tools.garmin.FitRecords`
            (``parse_fit_records``); its sport and start date are used when
            ``sport`` / ``date`` are not given.
        sport: Sport code (``running``, ``cycling``…).
        sensor: ``chest_strap`` or ``optical`` (``None`` = not given, a
            warning recalls that a chest strap is needed).
        date: ISO date of the test.

    Returns:
        An :class:`HRMaxTestResult`.

    Raises:
        ValueError: No series, unknown sensor or sport, or no 5-s window with
            a plausible heart rate.

    """
    if records is not None:
        time_sec, heart_rate = records.time_sec, records.heart_rate
        sport = sport or records.sport
        if date is None and getattr(records, "start", None) is not None:
            date = records.start.date().isoformat()
    if time_sec is None or heart_rate is None:
        raise ValueError("Give time_sec and heart_rate, or records.")
    if sensor is not None and sensor not in SENSORS:
        raise ValueError(f"Unknown sensor {sensor!r}; expected one of {SENSORS}.")
    sport = validate_sport(sport) or "other"

    peak = sustained_peak(time_sec, heart_rate)
    if not math.isfinite(peak.hr_max):
        raise ValueError("No 5-s window with a plausible heart rate.")
    t, hr = clean_heart_rate(time_sec, heart_rate)
    held = held_heart_rate(t, hr, SUSTAINED_SEC)

    before = t <= peak.time_sec
    high = held >= FINAL_EFFORT_PCT / 100.0 * peak.hr_max
    idx = np.flatnonzero(before)
    final = 0.0
    if len(idx):
        i = idx[-1]
        j = i
        while j > 0 and (high[j - 1] or not np.isfinite(held[j - 1])):
            j -= 1
        final = float(t[i] - t[j])
    near = np.isfinite(held) & (held >= peak.hr_max - PLATEAU_BPM)
    k = int(np.argmin(np.abs(t - peak.time_sec)))
    a = b = k
    while a > 0 and near[a - 1]:
        a -= 1
    while b < len(t) - 1 and near[b + 1]:
        b += 1
    plateau = bool(t[b] - t[a] >= PLATEAU_SEC)

    notes: list[str] = []
    status = "valid"
    if sensor == "optical":
        status = "invalid"
        notes.append(
            "Optical sensor: wrist sensors lose the beat at high intensity. "
            "Repeat the test with a chest strap."
        )
    elif sensor is None:
        notes.append("Sensor not given: an HRmax test needs a chest strap.")
    if final < MIN_FINAL_EFFORT_SEC:
        notes.append(
            f"Final effort of {final:.0f} s at ≥ 90 % of the peak (at least "
            f"{MIN_FINAL_EFFORT_SEC:.0f} s expected): probably not all-out."
        )
    if not plateau:
        notes.append(
            "The heart rate was still rising before the peak: the effort may have "
            "stopped before the maximum."
        )
    if status == "valid" and (final < MIN_FINAL_EFFORT_SEC or not plateau):
        status = "doubtful"
    if peak.isolated_spike:
        notes.append(
            f"A spike at {peak.raw_max:.0f} bpm lasted less than 5 s: sensor artefact, "
            f"not retained (HRmax held 5 s: {peak.hr_max:.0f} bpm)."
        )
    for note in notes:
        warnings.warn(note, stacklevel=2)
    return HRMaxTestResult(
        hr_max=float(round_bpm(peak.hr_max)),
        sport=sport,
        date=date,
        peak_time_sec=peak.time_sec,
        raw_max=peak.raw_max,
        final_effort_sec=final,
        plateau_reached=plateau,
        sensor=sensor,
        status=status,
        warnings=notes,
    )
