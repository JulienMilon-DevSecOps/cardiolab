"""Parsers for RR interval export files produced by Polar sensors."""

from __future__ import annotations

import csv
from pathlib import Path

# ======================
# PUBLIC API
# ======================


def parse_rr_file(filepath: str | Path) -> dict:
    """Parse an RR interval file exported by a Polar sensor.

    Automatically selects the appropriate parser based on the file extension:

    * ``.csv`` → column-based CSV (e.g. Polar Flow export).
    * ``.txt`` or ``.rr`` → single-column plain-text format (e.g. Elite HRV).

    Args:
        filepath: Path to the RR data file. Can be a string or a
            ``pathlib.Path`` object.

    Returns:
        Dictionary with the following keys:

        * ``"source"`` — filename without directory.
        * ``"format"`` — file extension (``".csv"``, ``".txt"``, …).
        * ``"rr_intervals"`` — list of RR intervals in milliseconds.
        * ``"count"`` — number of valid intervals read.
        * ``"duration_sec"`` — total recording duration in seconds.

    Raises:
        FileNotFoundError: If the file does not exist at ``filepath``.
        ValueError: If the file extension is not supported, or if no valid
            RR intervals could be extracted.

    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(filepath)

    suffix = filepath.suffix.lower()

    if suffix == ".csv":
        return _parse_csv(filepath)
    elif suffix in [".txt", ".rr"]:
        return _parse_txt(filepath)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


# ======================
# CSV PARSER
# ======================


def _parse_csv(filepath: Path) -> dict:
    """Parse a CSV file containing a column of RR intervals.

    Scans the header row for a column whose name contains ``"rr"``
    (case-insensitive) and reads all numeric values from that column,
    discarding non-positive entries and malformed rows.

    Args:
        filepath: Path to the CSV file.

    Returns:
        Standardised output dictionary (see ``parse_rr_file``).

    Raises:
        ValueError: If no column matching ``"rr"`` is found in the header.

    """
    rr_intervals: list[float] = []

    with open(filepath) as f:
        reader = csv.DictReader(f)

        rr_column = None
        for col in reader.fieldnames:
            if "rr" in col.lower():
                rr_column = col
                break

        if rr_column is None:
            raise ValueError("No RR column found in CSV")

        for row in reader:
            try:
                rr = float(row[rr_column])
                if rr > 0:
                    rr_intervals.append(rr)
            except (ValueError, KeyError):
                continue

    return _build_output(filepath, rr_intervals)


# ======================
# TXT PARSER
# ======================


def _parse_txt(filepath: Path) -> dict:
    """Parse a plain-text file with one RR interval per line.

    Expects a file where each non-empty line is a single numeric value
    representing one RR interval in milliseconds. Header lines and
    non-numeric rows are silently skipped.

    Example format::

        800
        810
        790
        ...

    Args:
        filepath: Path to the TXT or RR file.

    Returns:
        Standardised output dictionary (see ``parse_rr_file``).

    Raises:
        ValueError: If no valid RR intervals are found in the file.

    """
    rr_intervals: list[float] = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                rr = float(line)
                if rr > 0:
                    rr_intervals.append(rr)
            except ValueError:
                continue

    if not rr_intervals:
        raise ValueError("No valid RR intervals found in TXT file")

    return _build_output(filepath, rr_intervals)


# ======================
# COMMON OUTPUT
# ======================


def _build_output(filepath: Path, rr_intervals: list[float]) -> dict:
    """Assemble the standardised output dictionary.

    Args:
        filepath: Original file path, used to extract ``source`` and
            ``format`` metadata.
        rr_intervals: List of valid RR intervals in milliseconds.

    Returns:
        Dictionary with keys ``"source"``, ``"format"``, ``"rr_intervals"``,
        ``"count"``, and ``"duration_sec"``.

    """
    return {
        "source": filepath.name,
        "format": filepath.suffix.lower(),
        "rr_intervals": rr_intervals,
        "count": len(rr_intervals),
        "duration_sec": sum(rr_intervals) / 1000.0,
    }
