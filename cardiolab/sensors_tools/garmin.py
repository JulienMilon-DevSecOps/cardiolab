"""Parsers for Garmin FIT files and Garmin Connect CSV exports.

Requires the optional ``fitparse`` dependency for FIT file support::

    pip install cardiolab[garmin]

CSV parsing works without any optional dependency.
"""

from __future__ import annotations

import csv
from pathlib import Path

try:
    import fitparse as _fitparse

    _FITPARSE_AVAILABLE = True
except ImportError:
    _fitparse = None  # type: ignore[assignment]
    _FITPARSE_AVAILABLE = False

from cardiolab.signals.rr import RRSeries

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


def extract_training_session_garmin(filepath: str | Path) -> dict:
    """Extract a training session summary from a Garmin FIT file.

    Reads ``record`` messages (sampled at ~1 Hz) to compute the session
    duration and heart rate statistics.

    Args:
        filepath: Path to the Garmin ``.fit`` file.

    Returns:
        Dictionary with keys:

        * ``"duration_min"`` (:class:`float`) — total duration in minutes,
          derived from the first and last ``timestamp`` fields.
        * ``"hr_mean"`` (:class:`float`) — mean heart rate in bpm.
        * ``"hr_max"`` (:class:`float`) — maximum heart rate in bpm.

    Raises:
        ImportError: If ``fitparse`` is not installed.
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If no heart rate data is found in the FIT file.

    """
    _require_fitparse()

    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(filepath)

    fitfile = _fitparse.FitFile(str(filepath))
    heart_rates: list[float] = []
    timestamps: list = []

    for record in fitfile.get_messages("record"):
        hr = record.get_value("heart_rate")
        ts = record.get_value("timestamp")
        if hr is not None:
            heart_rates.append(float(hr))
        if ts is not None:
            timestamps.append(ts)

    if not heart_rates:
        raise ValueError(f"No heart rate data found in FIT file: {filepath.name}")

    duration_min = 0.0
    if len(timestamps) >= 2:
        delta = timestamps[-1] - timestamps[0]
        duration_min = delta.total_seconds() / 60.0

    return {
        "duration_min": round(duration_min, 2),
        "hr_mean": round(sum(heart_rates) / len(heart_rates), 1),
        "hr_max": float(max(heart_rates)),
    }


# ======================
# INTERNAL HELPERS
# ======================


def _require_fitparse() -> None:
    """Raise ImportError if fitparse is not available."""
    if not _FITPARSE_AVAILABLE:
        raise ImportError(
            "fitparse is required for Garmin FIT support: pip install cardiolab[garmin]"
        )
