"""Parsers for FIT activity files and Garmin Connect CSV exports.

FIT is the activity format of Garmin devices and of most training apps
(MyWhoosh, Zwift, Wahoo…). Three readers:

* :func:`parse_garmin_fit` — beat-to-beat intervals (``hrv`` messages, only
  recorded by a device paired with a chest strap, HRV logging on);
* :func:`parse_fit_records` — the per-second ``record`` messages: heart rate,
  power, cadence, speed (indoor trainers, power meters);
* :func:`extract_training_session_garmin` — the session summary;

and :func:`merge_fit_records`, which combines two recordings of the same
session (heart rate from the watch, power from the training app).

See ``docs/sensors/indoor_cycling.md`` for the recording set-ups that give
power, heart rate and beat intervals together.

Requires the optional ``fitparse`` dependency for FIT file support::

    pip install cardiolab[garmin]

CSV parsing works without any optional dependency.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

try:
    import fitparse as _fitparse

    _FITPARSE_AVAILABLE = True
except ImportError:
    _fitparse = None  # type: ignore[assignment]
    _FITPARSE_AVAILABLE = False

from cardiolab.signals.rr import RRSeries
from cardiolab.sports import normalize_sport

# ======================
# PUBLIC API
# ======================


def parse_garmin_fit(filepath: str | Path) -> RRSeries:
    """Extract RR intervals from a Garmin FIT file.

    Reads ``hrv`` messages embedded in the FIT file and converts the
    beat-to-beat intervals (stored in seconds) to milliseconds.

    Args:
        filepath: Path to the Garmin ``.fit`` file.

    Returns:
        :class:`RRSeries` built from all HRV intervals found in the file.

    Raises:
        ImportError: If ``fitparse`` is not installed
            (``pip install cardiolab[garmin]``).
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the FIT file contains no HRV messages.

    """
    _require_fitparse()

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(filepath)

    fitfile = _fitparse.FitFile(str(filepath))
    rr_intervals: list[float] = []

    for record in fitfile.get_messages("hrv"):
        for data in record:
            if data.name == "time" and data.value:
                for interval in data.value:
                    if interval is not None and interval > 0:
                        rr_intervals.append(interval * 1000.0)

    if not rr_intervals:
        raise ValueError(f"No HRV messages found in FIT file: {filepath.name}")

    return RRSeries(rr_intervals)


def parse_garmin_csv(filepath: str | Path) -> RRSeries:
    """Parse a Garmin RR interval CSV export.

    Detects the RR column by scanning the header for any name containing
    ``"rr"`` (case-insensitive).  Positive numeric values are kept; negative,
    zero, and non-numeric entries are silently skipped.

    Args:
        filepath: Path to the Garmin CSV file.

    Returns:
        :class:`RRSeries` built from the valid RR intervals.

    Raises:
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If no RR column is found, the file is empty, or no
            valid intervals could be extracted.

    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(filepath)

    rr_intervals: list[float] = []

    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("Empty or unreadable CSV file")

        fields_lower = {name.lower().strip(): name for name in reader.fieldnames}
        rr_col = next((fields_lower[k] for k in fields_lower if "rr" in k), None)

        if rr_col is None:
            raise ValueError("No RR interval column found in Garmin CSV")

        for row in reader:
            try:
                v = float(row[rr_col])
                if v > 0:
                    rr_intervals.append(v)
            except (ValueError, TypeError):
                continue

    if not rr_intervals:
        raise ValueError(f"No valid RR intervals found in: {filepath.name}")

    return RRSeries(rr_intervals)


@dataclass
class FitRecords:
    """Per-second samples of a FIT activity (``record`` messages).

    Every series has one value per record, ``nan`` where the field is
    missing. A heart rate of 0 (sensor drop-out) is stored as ``nan``; a
    power or cadence of 0 is a real value (freewheeling) and is kept.

    Attributes:
        start: Timestamp of the first record (UTC, as written in the file).
        time_sec: Seconds since the first record.
        heart_rate: Heart rate (bpm).
        power: Power (W).
        cadence: Cadence (rpm, or steps per minute for running).
        speed: Speed (m/s; ``enhanced_speed`` when present).
        sport: Sport code of the reference list (``"other"`` if absent).
        sport_raw: FIT ``sport`` value as read, for diagnosis.

    """

    start: datetime
    time_sec: np.ndarray
    heart_rate: np.ndarray
    power: np.ndarray
    cadence: np.ndarray
    speed: np.ndarray
    sport: str = "other"
    sport_raw: str | None = None

    @property
    def duration_sec(self) -> float:
        """Time between the first and the last record (s)."""
        return float(self.time_sec[-1]) if len(self.time_sec) else 0.0

    def has(self, field: str) -> bool:
        """Return ``True`` when ``field`` has at least one recorded value."""
        return bool(np.any(np.isfinite(getattr(self, field))))

    def intensity(self, field: str = "power") -> tuple[np.ndarray, np.ndarray]:
        """Return ``(time_sec, values)`` of ``field`` without missing samples.

        Ready for the ``intensity`` argument of
        :func:`cardiolab.protocols.dfa_thresholds.dfa_thresholds`, whose time
        counts from the first beat: both start at the beginning of the
        activity when the beats come from the same file
        (:func:`parse_garmin_fit`).

        Args:
            field: ``"power"`` (W), ``"speed"`` (m/s), ``"cadence"`` or
                ``"heart_rate"``.

        Raises:
            ValueError: If ``field`` is unknown or has no recorded value.

        """
        if field not in ("power", "speed", "cadence", "heart_rate"):
            raise ValueError(f"Unknown record field: {field!r}")
        values = getattr(self, field)
        ok = np.isfinite(values)
        if not np.any(ok):
            raise ValueError(f"No {field} recorded in this file")
        return self.time_sec[ok], values[ok]


def parse_fit_records(filepath: str | Path) -> FitRecords:
    """Read the per-second samples of a FIT activity file.

    Works with any FIT activity: Garmin watches and bike computers, indoor
    training apps (tested with a MyWhoosh export: power, cadence, speed and
    heart rate at 1 Hz).

    Args:
        filepath: Path to the ``.fit`` file.

    Returns:
        :class:`FitRecords` with heart rate, power, cadence and speed.

    Raises:
        ImportError: If ``fitparse`` is not installed.
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the file has no timestamped ``record`` message.

    """
    _require_fitparse()

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(filepath)

    fitfile = _fitparse.FitFile(str(filepath))
    records = _read_records(fitfile)
    if records is None:
        raise ValueError(f"No timestamped record messages in FIT file: {filepath.name}")
    sport_raw, sub_sport_raw = _read_sport(fitfile)
    records.sport = normalize_sport(sport_raw, sub_sport_raw)
    records.sport_raw = sport_raw
    return records


RECORD_FIELDS = ("heart_rate", "power", "cadence", "speed")
"""Series of :class:`FitRecords`, in the order :func:`merge_fit_records` fills them."""

MERGE_MAX_GAP_SEC = 30.0
"""Longest gap (s) bridged by interpolation when merging two recordings."""


def merge_fit_records(
    first: FitRecords,
    second: FitRecords,
    *,
    second_offset_sec: float = 0.0,
    max_gap_sec: float = MERGE_MAX_GAP_SEC,
) -> FitRecords:
    """Merge two recordings of the same session into one, on a 1-second grid.

    Set-up C of ``docs/sensors/indoor_cycling.md``: the watch records the
    heart rate (chest strap), the training app records the power. Both files
    are aligned on their **timestamps** (UTC, as written in the files) and
    resampled every second over the period they **both** cover.

    Each series comes from the first file that has it (``first`` wins when
    both do): heart rate from the watch, power, cadence and speed from the
    app. Gaps up to ``max_gap_sec`` are filled by linear interpolation —
    watches in "smart recording" write a sample only every 1–15 s; longer
    gaps (pause, sensor drop-out) stay ``nan``.

    Beat intervals (``hrv`` messages) are not part of the records: read them
    with :func:`parse_garmin_fit` from the watch file. They start with the
    watch recording, while ``time_sec`` of the result counts from its own
    ``start`` (the first second both files cover): add
    ``(merged.start - watch.start).total_seconds()`` to the merged times
    before pairing them with the beats.

    Args:
        first: Recording that takes precedence (usually the watch).
        second: Other recording (usually the training app).
        second_offset_sec: Seconds added to the timestamps of ``second`` to
            correct a clock difference between the two devices (positive when
            its clock is behind).
        max_gap_sec: Longest gap filled by interpolation (s).

    Returns:
        :class:`FitRecords` at 1 Hz, starting at the first common second.

    Raises:
        ValueError: If the two recordings do not overlap, or ``max_gap_sec``
            is negative.

    """
    if max_gap_sec < 0:
        raise ValueError("max_gap_sec must not be negative")
    abs_first = _absolute_seconds(first, first.start, 0.0)
    abs_second = _absolute_seconds(second, first.start, second_offset_sec)
    t_start = np.ceil(max(abs_first[0], abs_second[0]))
    t_end = np.floor(min(abs_first[-1], abs_second[-1]))
    if t_end <= t_start:
        raise ValueError("The two recordings do not overlap in time")
    grid = np.arange(t_start, t_end + 1.0)

    series: dict[str, np.ndarray] = {}
    for field in RECORD_FIELDS:
        source, times = (first, abs_first) if first.has(field) else (second, abs_second)
        series[field] = _resample(times, getattr(source, field), grid, max_gap_sec)

    sport, sport_raw = (
        (first.sport, first.sport_raw)
        if first.sport != "other"
        else (second.sport, second.sport_raw)
    )
    return FitRecords(
        start=first.start + timedelta(seconds=float(t_start)),
        time_sec=grid - t_start,
        sport=sport,
        sport_raw=sport_raw,
        **series,
    )


def extract_training_session_garmin(filepath: str | Path) -> dict:
    """Extract a training session summary from a Garmin FIT file.

    Reads ``record`` messages (sampled at ~1 Hz) to compute the session
    duration, heart rate and power statistics, and the ``session`` /
    ``sport`` messages for the activity sport.

    Since 0.6.0 the heart rate is optional: a file without it (indoor app
    recording power only, watch not paired) gives ``hr_mean = None`` — the
    session can still be saved, its heart-rate load stays pending. Heart rate
    values of 0 (sensor drop-outs) are ignored.

    Args:
        filepath: Path to the ``.fit`` file.

    Returns:
        Dictionary with keys:

        * ``"duration_min"`` (:class:`float`) — total duration in minutes,
          derived from the first and last ``timestamp`` fields.
        * ``"hr_mean"`` / ``"hr_max"`` (:class:`float` | ``None``) — mean and
          maximum heart rate (bpm), ``None`` without heart rate.
        * ``"power_mean"`` / ``"power_max"`` (:class:`float` | ``None``) —
          mean and maximum power (W), ``None`` without power.
        * ``"sport"`` (:class:`str`) — sport code of the reference list
          (:func:`cardiolab.sports.normalize_sport` of the FIT ``sport`` and
          ``sub_sport`` fields); ``"other"`` when the file has no sport.
        * ``"sport_raw"`` (:class:`str` | ``None``) — FIT ``sport`` value as
          read from the file, for diagnosis.

    Raises:
        ImportError: If ``fitparse`` is not installed.
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the file has no timestamped ``record`` message.

    """
    rec = parse_fit_records(filepath)
    return {
        "duration_min": round(rec.duration_sec / 60.0, 2),
        "hr_mean": _rounded_mean(rec.heart_rate),
        "hr_max": _finite_max(rec.heart_rate),
        "power_mean": _rounded_mean(rec.power),
        "power_max": _finite_max(rec.power),
        "sport": rec.sport,
        "sport_raw": rec.sport_raw,
    }


# ======================
# INTERNAL HELPERS
# ======================


def _read_records(fitfile) -> FitRecords | None:
    """Collect the timestamped ``record`` messages, or ``None`` if there is none."""
    stamps: list[datetime] = []
    hr: list[float] = []
    power: list[float] = []
    cadence: list[float] = []
    speed: list[float] = []
    for record in fitfile.get_messages("record"):
        ts = record.get_value("timestamp")
        if ts is None:
            continue
        stamps.append(ts)
        h = record.get_value("heart_rate")
        hr.append(float(h) if h else np.nan)  # 0 = drop-out
        power.append(_as_float(record.get_value("power")))
        cadence.append(_as_float(record.get_value("cadence")))
        spd = record.get_value("enhanced_speed")
        speed.append(_as_float(spd if spd is not None else record.get_value("speed")))
    if not stamps:
        return None
    t0 = stamps[0]
    return FitRecords(
        start=t0,
        time_sec=np.array([(t - t0).total_seconds() for t in stamps]),
        heart_rate=np.array(hr),
        power=np.array(power),
        cadence=np.array(cadence),
        speed=np.array(speed),
    )


def _absolute_seconds(
    records: FitRecords, origin: datetime, offset_sec: float
) -> np.ndarray:
    """Return the record times of ``records`` in seconds since ``origin``."""
    shift = (records.start - origin).total_seconds() + offset_sec
    return np.asarray(records.time_sec, dtype=float) + shift


def _resample(
    times: np.ndarray, values: np.ndarray, grid: np.ndarray, max_gap_sec: float
) -> np.ndarray:
    """Interpolate ``values`` on ``grid``; ``nan`` across gaps longer than ``max_gap_sec``."""
    values = np.asarray(values, dtype=float)
    ok = np.isfinite(values)
    out = np.full(len(grid), np.nan)
    if not np.any(ok):
        return out
    t, v = times[ok], values[ok]
    inside = (grid >= t[0]) & (grid <= t[-1])
    out[inside] = np.interp(grid[inside], t, v)
    # Distance from each grid point to the samples around it
    right = np.searchsorted(t, grid[inside], side="left")
    right = np.clip(right, 0, len(t) - 1)
    left = np.clip(right - 1, 0, len(t) - 1)
    exact = t[right] == grid[inside]
    gap = np.where(exact, 0.0, t[right] - t[left])
    out[np.flatnonzero(inside)[gap > max_gap_sec]] = np.nan
    return out


def _as_float(value) -> float:
    """Return ``value`` as a float, ``nan`` when missing."""
    return float(value) if value is not None else np.nan


def _rounded_mean(values: np.ndarray) -> float | None:
    """Mean of the finite values rounded to 0.1, or ``None`` without any."""
    ok = values[np.isfinite(values)]
    return round(float(ok.mean()), 1) if len(ok) else None


def _finite_max(values: np.ndarray) -> float | None:
    """Maximum of the finite values, or ``None`` without any."""
    ok = values[np.isfinite(values)]
    return float(ok.max()) if len(ok) else None


def _read_sport(fitfile) -> tuple[str | None, str | None]:
    """Return the activity ``(sport, sub_sport)`` of a FIT file, or ``(None, None)``.

    Looks at the ``session`` messages first (one per activity), then at the
    ``sport`` message; the first one carrying a ``sport`` value wins.
    """
    for message_name in ("session", "sport"):
        for message in fitfile.get_messages(message_name):
            sport = message.get_value("sport")
            if sport is not None:
                sub_sport = message.get_value("sub_sport")
                return str(sport), (str(sub_sport) if sub_sport is not None else None)
    return None, None


def _require_fitparse() -> None:
    """Raise ImportError if fitparse is not available."""
    if not _FITPARSE_AVAILABLE:
        raise ImportError(
            "fitparse is required for Garmin FIT support: pip install cardiolab[garmin]"
        )
