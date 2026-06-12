"""Parsers for HRV data exported from HRV4Training."""

from __future__ import annotations

import contextlib
import csv
from pathlib import Path

from cardiolab.signals.rr import RRSeries

# ======================
# PUBLIC API
# ======================


def parse_hrv4training_csv(filepath: str | Path) -> list[dict]:
    """Parse a CSV file exported from the HRV4Training mobile app.

    Each row in the export represents one measurement session. The function
    handles both summary-only exports and exports that include raw RR
    intervals in a dedicated column.

    Expected columns (matched case-insensitively):

    * ``date`` — session date (YYYY-MM-DD or ISO format).
    * ``rMSSD`` — RMSSD value in milliseconds.
    * ``RR intervals`` *(optional)* — semicolon-separated RR intervals in ms.

    Args:
        filepath: Path to the HRV4Training CSV export file.

    Returns:
        List of dicts, one per valid session row, each with keys:

        * ``"date"`` (:class:`str`) — session date as found in the file.
        * ``"rmssd"`` (:class:`float` | ``None``) — RMSSD value, or ``None``
          if the column is absent or the value is not numeric.
        * ``"rr_intervals"`` (:class:`list[float]` | ``None``) — raw RR
          intervals in milliseconds, or ``None`` when the column is absent or
          empty.

    Raises:
        FileNotFoundError: If ``filepath`` does not exist.
        ValueError: If the file has no readable header or no ``date`` column.

    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(filepath)

    records: list[dict] = []

    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("Empty or unreadable CSV file")

        fields_lower = {name.lower().strip(): name for name in reader.fieldnames}

        date_col = _find_col(fields_lower, ["date"])
        rmssd_col = _find_col(fields_lower, ["rmssd", "rmssd recording"])
        rr_col = _find_col(fields_lower, ["rr intervals", "rr_intervals"])

        if date_col is None:
            raise ValueError("No 'date' column found in HRV4Training CSV")

        for row in reader:
            date_val = row.get(date_col, "").strip()
            if not date_val:
                continue

            rmssd_val: float | None = None
            if rmssd_col is not None:
                with contextlib.suppress(ValueError, TypeError):
                    rmssd_val = float(row[rmssd_col])

            rr_intervals: list[float] | None = None
            if rr_col is not None:
                raw = row.get(rr_col, "").strip()
                if raw:
                    parsed: list[float] = []
                    for token in raw.split(";"):
                        try:
                            v = float(token.strip())
                            if v > 0:
                                parsed.append(v)
                        except ValueError:
                            continue
                    if parsed:
                        rr_intervals = parsed

            records.append(
                {
                    "date": date_val,
                    "rmssd": rmssd_val,
                    "rr_intervals": rr_intervals,
                }
            )

    return records


def to_rrseries(record: dict) -> RRSeries:
    """Build an :class:`RRSeries` from an HRV4Training session record.

    Args:
        record: Dict produced by :func:`parse_hrv4training_csv`. Must contain
            a non-empty ``"rr_intervals"`` list.

    Returns:
        :class:`RRSeries` built from the record's RR intervals.

    Raises:
        ValueError: If the record contains no RR interval data, which is
            the case for summary-only HRV4Training exports.

    """
    rr_intervals = record.get("rr_intervals")
    if not rr_intervals:
        raise ValueError(
            f"No RR intervals in record for {record.get('date', '?')} — "
            "HRV4Training summary exports do not always include raw RR data."
        )
    return RRSeries(rr_intervals)


# ======================
# INTERNAL HELPERS
# ======================


def _find_col(fields_lower: dict[str, str], candidates: list[str]) -> str | None:
    """Return the original column name matching one of the candidate keys.

    Args:
        fields_lower: Mapping of lowercased field names to original names.
        candidates: Lowercased candidate column names, checked in order.

    Returns:
        The original (un-lowercased) column name, or ``None`` if not found.

    """
    for candidate in candidates:
        if candidate in fields_lower:
            return fields_lower[candidate]
    return None
