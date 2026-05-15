"""Batch import pipeline: converts raw sensor files to JSON session records."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cardiolab.sensors_tools.polar import parse_rr_file

raw_dir = Path("cardiolab/datasets/raw")


def import_all(output_dir: str = "cardiolab/datasets/resting") -> None:
    """Convert all raw RR files in the raw directory to JSON session records.

    Scans ``cardiolab/datasets/raw`` for any file supported by
    ``parse_rr_file`` (``.txt``, ``.csv``), parses each one, and writes a
    structured JSON record to ``output_dir``. Already-imported files are
    skipped to avoid duplicates.

    The output JSON contains:

    * ``"date"`` — extracted from the filename, or today's date as fallback.
    * ``"device"`` — hardcoded to ``"Polar H10"``.
    * ``"position"`` — hardcoded to ``"supine"``.
    * ``"source_file"`` — original filename.
    * ``"rr_intervals"`` — list of RR intervals in milliseconds.
    * ``"duration"`` — total recording duration in seconds.

    Args:
        output_dir: Destination directory for the JSON records. Created
            automatically if it does not exist. Defaults to
            ``"cardiolab/datasets/resting"``.

    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = list(raw_dir.glob("*"))

    if not files:
        print("No files found in datasets/raw")
        return

    for file in files:
        try:
            data = parse_rr_file(file)

            date_str = _extract_date(file.name)

            output = {
                "date": date_str,
                "device": "Polar H10",
                "position": "supine",
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
