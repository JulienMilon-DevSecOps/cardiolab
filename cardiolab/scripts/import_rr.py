"""Batch import pipeline: converts raw sensor files to JSON session records.

Directory layout expected under ``cardiolab/datasets/raw/``::

    datasets/raw/
    ├── resting/       ← 5-min supine recordings (.txt / .csv)
    └── orthostatic/   ← supine + standing recordings (.txt / .csv)

Call ``import_all(protocol="resting")`` or ``import_all(protocol="orthostatic")``
to convert the corresponding subdirectory to JSON session records.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cardiolab.sensors_tools.polar import parse_rr_file

_BASE_RAW = Path("cardiolab/datasets/raw")

# Maps a protocol name to (raw_input_dir, json_output_dir, position_field)
_PROTOCOL_DIRS: dict[str, tuple[str, str, str]] = {
    "resting": (
        str(_BASE_RAW / "resting"),
        "cardiolab/datasets/resting",
        "supine",
    ),
    "orthostatic": (
        str(_BASE_RAW / "orthostatic"),
        "cardiolab/datasets/orthostatic",
        "orthostatic",
    ),
}


def import_all(
    protocol: str = "resting",
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> None:
    """Convert raw RR files for a given protocol to JSON session records.

    Scans the raw input directory for any file supported by ``parse_rr_file``
    (``.txt``, ``.csv``), parses each one, and writes a structured JSON record
    to ``output_dir``. Already-imported files are skipped to avoid duplicates.

    Default directory layout::

        datasets/raw/resting/      → datasets/resting/
        datasets/raw/orthostatic/  → datasets/orthostatic/

    The output JSON contains:

    * ``"date"`` — extracted from the filename, or today's date as fallback.
    * ``"device"`` — hardcoded to ``"Polar H10"``.
    * ``"position"`` — ``"supine"`` for resting, ``"orthostatic"`` for orthostatic.
    * ``"source_file"`` — original filename.
    * ``"rr_intervals"`` — list of RR intervals in milliseconds.
    * ``"duration"`` — total recording duration in seconds.

    Args:
        protocol: Protocol name — ``"resting"`` or ``"orthostatic"``.
            Determines default input/output directories and the ``position``
            metadata field.
        input_dir: Override for the raw input directory. When ``None``,
            derived from ``protocol``.
        output_dir: Override for the JSON output directory. When ``None``,
            derived from ``protocol``.

    Raises:
        ValueError: If ``protocol`` is not a known protocol name.

    """
    if protocol not in _PROTOCOL_DIRS:
        known = ", ".join(f'"{p}"' for p in _PROTOCOL_DIRS)
        raise ValueError(f"Unknown protocol {protocol!r}. Known protocols: {known}.")

    default_in, default_out, position = _PROTOCOL_DIRS[protocol]
    raw_path = Path(input_dir or default_in)
    output_path = Path(output_dir or default_out)
    output_path.mkdir(parents=True, exist_ok=True)

    files = list(raw_path.glob("*"))

    if not files:
        print(f"No files found in {raw_path}")
        return

    for file in files:
        try:
            data = parse_rr_file(file)

            date_str = _extract_date(file.name)

            output = {
                "date": date_str,
                "device": "Polar H10",
                "position": position,
                "source_file": file.name,
                "rr_intervals": data["rr_intervals"],
                "duration": data["duration_sec"],
            }

            out_path = output_path / f"{date_str}.json"

            if out_path.exists():
                print(f"Skipped (already exists): {out_path.name}")
                continue

            with open(out_path, "w") as f:
                json.dump(output, f, indent=2)

            print(f"Imported → {out_path.name}")

        except Exception as e:
            print(f"Error with {file.name}: {e}")


# ======================
# HELPERS
# ======================


def _extract_date(filename: str) -> str:
    """Extract an ISO date string from a filename.

    Assumes the date is the part of the filename before the first dot.
    Falls back to today's date if parsing fails.

    Args:
        filename: Bare filename (without directory), e.g.
            ``"2026-04-24 07-52-36.txt"``.

    Returns:
        ISO date string in ``YYYY-MM-DD`` format, either extracted from the
        filename or derived from the current date.

    """
    try:
        return filename.split(".")[0]
    except Exception:
        return datetime.today().date().isoformat()
