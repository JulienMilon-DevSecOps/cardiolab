"""Generic PPG file reader — any optical sensor exporting its raw pulse wave.

Few consumer devices export the raw PPG: most watches only give a heart rate,
or intervals they computed themselves. The sources that do are research or
developer tools (sensor SDKs, loggers) and phone camera apps (finger on the
lens, one brightness value per frame). Their CSV layouts differ, so this
reader takes the column names instead of guessing a format:

* a column of PPG values (``value_column``);
* either a time column (``time_column``, in ``s``, ``ms``, ``us`` or ``ns``)
  or a fixed ``sampling_rate``.

The result is a :class:`~cardiolab.signals.ppg.PPGSignal`; call
:meth:`~cardiolab.signals.ppg.PPGSignal.to_rr` for the intervals.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from cardiolab.signals.ppg import PPGSignal

_TIME_UNITS = {"s": 1.0, "ms": 1e-3, "us": 1e-6, "ns": 1e-9}


def _number(text: str) -> float:
    return float(text.strip().replace(",", ".")) if text.strip() else float("nan")


def parse_ppg_csv(
    filepath: str | Path,
    value_column: str,
    *,
    time_column: str | None = None,
    time_unit: str = "s",
    sampling_rate: float | None = None,
    delimiter: str | None = None,
    source: str = "unknown",
    invert: bool = False,
) -> PPGSignal:
    """Read a raw PPG from a CSV file.

    Args:
        filepath: CSV file with a header line.
        value_column: Name of the column holding the PPG values.
        time_column: Name of the time column (optional when
            ``sampling_rate`` is given).
        time_unit: Unit of ``time_column`` — ``s``, ``ms``, ``us`` or ``ns``.
        sampling_rate: Sampling rate in Hz, when there is no time column.
        delimiter: Column separator; detected (``,`` ``;`` tab) when ``None``.
        source: ``finger``, ``wrist``, ``ear``, ``camera`` or ``unknown``.
        invert: ``True`` when the systolic peak is a minimum (camera
            brightness).

    Returns:
        The :class:`~cardiolab.signals.ppg.PPGSignal`. Rows with an empty or
        non-numeric value are skipped.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: Unknown column or time unit, no time axis, or fewer than
            2 valid rows.

    """
    filepath = Path(filepath)
    if not filepath.is_file():
        raise FileNotFoundError(filepath)
    if time_unit not in _TIME_UNITS:
        raise ValueError(
            f"time_unit must be one of {list(_TIME_UNITS)}, got {time_unit!r}."
        )
    if time_column is None and sampling_rate is None:
        raise ValueError("Give time_column or sampling_rate.")

    with filepath.open(newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
            except csv.Error:  # a single column: nothing to detect
                delimiter = ","
        reader = csv.DictReader(f, delimiter=delimiter)
        fields = [c.strip() for c in (reader.fieldnames or [])]
        reader.fieldnames = fields
        for column in (value_column, time_column):
            if column is not None and column not in fields:
                raise ValueError(f"Column {column!r} not found; columns: {fields}.")
        values, times = [], []
        for row in reader:
            try:
                v = _number(row[value_column])
                t = _number(row[time_column]) if time_column else 0.0
            except (TypeError, ValueError):
                continue
            if np.isfinite(v) and np.isfinite(t):
                values.append(v)
                times.append(t)

    if len(values) < 2:
        raise ValueError(f"Fewer than 2 valid PPG samples in {filepath.name}.")
    timestamps = None
    if time_column is not None:
        timestamps = np.asarray(times) * _TIME_UNITS[time_unit]
        timestamps = timestamps - timestamps[0]
    return PPGSignal(
        np.asarray(values),
        sampling_rate=sampling_rate if time_column is None else None,
        timestamps=timestamps,
        source=source,
        invert=invert,
        metadata={"file": filepath.name},
    )
