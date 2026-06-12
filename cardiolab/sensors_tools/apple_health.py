"""Parsers for HRV data exported from the Apple Health app.

.. important::

    The standard Apple Health XML export does **not** contain raw RR intervals.
    Only pre-computed metrics are available:

    * **SDNN** — via ``HKQuantityTypeIdentifierHeartRateVariabilitySDNN``
    * **Resting heart rate** — via ``HKQuantityTypeIdentifierRestingHeartRate``

    Without raw inter-beat intervals it is impossible to recompute RMSSD, HF
    power, DFA α1, or sample entropy.  The ``rmssd`` field in the returned
    records will therefore always be ``None`` for standard exports.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

# Apple Health record type identifiers
_TYPE_SDNN = "HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
_TYPE_RESTING_HR = "HKQuantityTypeIdentifierRestingHeartRate"

# ======================
# PUBLIC API
# ======================


def parse_apple_health_export(filepath: str | Path) -> list[dict]:
    """Parse the Apple Health ``export.xml`` file for HRV-related records.

    Reads all ``<Record>`` elements from the export and returns those that
    carry HRV or heart-rate data (SDNN and resting HR).  One dict is
    returned per ``<Record>`` element — multiple measurements on the same
    day produce multiple entries.

    Args:
        filepath: Path to the Apple Health ``export.xml`` file.

    Returns:
        List of dicts, one per relevant record, with keys:

        * ``"date"`` (:class:`str`) — measurement date (``YYYY-MM-DD``).
        * ``"sdnn"`` (:class:`float` | ``None``) — SDNN value in ms, or
          ``None`` when the record is not an HRV measurement.
        * ``"rmssd"`` (:class:`float` | ``None``) — always ``None`` for
          standard Apple Health exports (raw RR intervals are unavailable).
        * ``"resting_hr"`` (:class:`float` | ``None``) — resting heart rate
          in bpm, or ``None`` when the record is not a resting-HR measurement.
        * ``"source"`` (:class:`str`) — name of the source device or app.

    Raises:
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the file cannot be parsed as XML or contains no
            ``<HealthData>`` root element.

    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(filepath)

    try:
        tree = ET.parse(filepath)  # noqa: S314
    except ET.ParseError as exc:
        raise ValueError(f"Cannot parse XML file: {filepath.name}") from exc

    root = tree.getroot()
    if root.tag != "HealthData":
        raise ValueError(f"Expected root element <HealthData>, got <{root.tag}>")

    records: list[dict] = []

    for elem in root.iter("Record"):
        record_type = elem.get("type", "")

        if record_type not in (_TYPE_SDNN, _TYPE_RESTING_HR):
            continue

        start_date = elem.get("startDate", "")
        date_str = start_date[:10] if start_date else ""
        if not date_str:
            continue

        value_str = elem.get("value", "")
        try:
            value = float(value_str)
        except ValueError:
            continue

        source = elem.get("sourceName", "")

        if record_type == _TYPE_SDNN:
            records.append(
                {
                    "date": date_str,
                    "sdnn": value,
                    "rmssd": None,
                    "resting_hr": None,
                    "source": source,
                }
            )
        else:  # _TYPE_RESTING_HR
            records.append(
                {
                    "date": date_str,
                    "sdnn": None,
                    "rmssd": None,
                    "resting_hr": value,
                    "source": source,
                }
            )

    return records


def extract_hrv_samples(filepath: str | Path) -> list[dict]:
    """Extract one HRV summary per day from an Apple Health export.

    Aggregates all records for each calendar day: SDNN is averaged across
    all measurements of the day, and resting HR is taken from the first
    resting-HR record found.

    Args:
        filepath: Path to the Apple Health ``export.xml`` file.

    Returns:
        List of dicts sorted by date (ascending), one per day that has at
        least one HRV or resting-HR measurement:

        * ``"date"`` (:class:`str`) — calendar day (``YYYY-MM-DD``).
        * ``"sdnn"`` (:class:`float` | ``None``) — mean SDNN across all
          measurements of the day, or ``None`` if no SDNN record.
        * ``"rmssd"`` (:class:`float` | ``None``) — always ``None`` for
          standard Apple Health exports.

    Raises:
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the file cannot be parsed.

    """
    raw = parse_apple_health_export(filepath)

    # Group by date
    by_date: dict[str, dict] = {}
    for rec in raw:
        date = rec["date"]
        if date not in by_date:
            by_date[date] = {"sdnn_values": [], "rmssd": None}

        if rec["sdnn"] is not None:
            by_date[date]["sdnn_values"].append(rec["sdnn"])

    result: list[dict] = []
    for date in sorted(by_date):
        sdnn_values = by_date[date]["sdnn_values"]
        result.append(
            {
                "date": date,
                "sdnn": sum(sdnn_values) / len(sdnn_values) if sdnn_values else None,
                "rmssd": None,
            }
        )

    return result
