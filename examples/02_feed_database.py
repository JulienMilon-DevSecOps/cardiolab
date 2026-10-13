"""Compute HRV features from raw resting RR files and persist them to the database.

Run this script after each new recording session, or in batch to import all
existing sessions at once. The upsert strategy makes re-running safe: existing
rows are updated rather than duplicated.

Workflow
--------
1. Find all raw RR files (``.txt``, ``.csv``, ``.rr``) in ``cardiolab/datasets/raw/resting/``.
2. Parse each one with ``parse_rr_file()``, build an ``RRSeries`` and compute ``HRVFeatures`` via ``resting_hrv()``.
3. Persist every session to the database under your ``USER_ID``.

Prerequisites
-------------
* ``01_setup_database.py`` must have been run at least once.
* ``.env`` file with ``DB_*`` variables and a stable ``USER_ID`` (UUID).
* Raw Polar / Elite HRV exports in ``cardiolab/datasets/raw/resting/`` (ignored by
  git). The session date is the file name without extension, e.g.
  ``2026-04-24 07-52-36.txt``.

Usage
-----
Run from the project root::

    python examples/02_feed_database.py

"""

from __future__ import annotations

import dataclasses
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from cardiolab.database.repository import HRVRepository
from cardiolab.protocols.resting import resting_hrv
from cardiolab.sensors_tools import parse_rr_file
from cardiolab.signals.rr import RRSeries

load_dotenv()

_raw_user_id = os.environ.get("USER_ID")
if _raw_user_id is None:
    _generated = uuid.uuid4()
    print(
        f"[WARNING] USER_ID not found in environment.\n"
        f"          A temporary UUID has been generated for this run:\n"
        f"          USER_ID={_generated}\n"
        f"          Add this line to your .env file to keep it stable.\n"
    )
    USER_ID = str(_generated)
else:
    USER_ID = str(uuid.UUID(_raw_user_id))


RAW_DIR = "cardiolab/datasets/raw/resting"
_RR_SUFFIXES = {".txt", ".csv", ".rr"}


def load_features_from_files(raw_dir: str = RAW_DIR) -> list:
    """Compute HRVFeatures from each raw RR file found in *raw_dir*."""
    files = sorted(p for p in Path(raw_dir).glob("*") if p.suffix in _RR_SUFFIXES)
    if not files:
        print(f"No RR files (.txt / .csv / .rr) found in: {raw_dir}")
        return []

    features = []
    for filepath in files:
        data = parse_rr_file(filepath)
        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)
        # Session date = file name without extension (e.g. "2026-04-24 07-52-36")
        features.append(dataclasses.replace(result, date=filepath.stem))

    return features


def feed(raw_dir: str = RAW_DIR) -> None:
    """Full feed pipeline: compute HRV features and persist to DB."""
    print("=== cardiolab — feed database ===\n")
    print(f"User ID : {USER_ID}")

    features = load_features_from_files(raw_dir)
    if not features:
        return

    print(f"Sessions found : {len(features)}")

    with HRVRepository.from_env() as repo:
        repo.save_features(features, user_id=USER_ID)
        print(
            f"Saved to table  : '{repo.table_name}' (upsert — duplicates are updated)"
        )

    print(
        f"\n{'Date':<25} {'RMSSD':>7} {'SDNN':>7} {'HR':>6} {'HF_nu':>7} {'LF/HF':>7}"
    )
    print("-" * 65)
    for f in features:
        print(
            f"{str(f.date):<25} {f.rmssd:>7.1f} {f.sdnn:>7.1f} "
            f"{f.mean_hr:>6.1f} {f.hf_nu:>7.2f} {f.lf_hf:>7.2f}"
        )


if __name__ == "__main__":
    feed()
