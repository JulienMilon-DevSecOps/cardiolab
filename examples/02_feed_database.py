"""Compute HRV features from resting JSON session files and persist them to the database.

Run this script after each new recording session, or in batch to import all
existing sessions at once. The upsert strategy makes re-running safe: existing
rows are updated rather than duplicated.

Workflow
--------
1. Find all ``.json`` files in ``cardiolab/datasets/resting/``.
2. Build an ``RRSeries`` for each file and compute ``HRVFeatures`` via ``resting_hrv()``.
3. Persist every session to the database under your ``USER_ID``.

Prerequisites
-------------
* ``01_setup_database.py`` must have been run at least once.
* ``.env`` file with ``DB_*`` variables and a stable ``USER_ID`` (UUID).
* JSON files in ``cardiolab/datasets/resting/`` (use ``04_import_resting.py``
  to convert raw Polar exports).

Usage
-----
Run from the project root::

    python example/02_feed_database.py

"""

from __future__ import annotations

import dataclasses
import glob
import json
import os
import uuid

from dotenv import load_dotenv

from cardiolab.database.repository import HRVRepository
from cardiolab.protocols.resting import resting_hrv
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


def load_features_from_json(pattern: str = "cardiolab/datasets/resting/*.json") -> list:
    """Compute HRVFeatures from each JSON file matched by *pattern*."""
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No JSON files found at: {pattern}")
        return []

    features = []
    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)
        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)
        features.append(dataclasses.replace(result, date=data["date"]))

    return features


def feed(pattern: str = "cardiolab/datasets/resting/*.json") -> None:
    """Full feed pipeline: compute HRV features and persist to DB."""
    print("=== cardiolab — feed database ===\n")
    print(f"User ID : {USER_ID}")

    features = load_features_from_json(pattern)
    if not features:
        return

    print(f"Sessions found : {len(features)}")

    with HRVRepository.from_env() as repo:
        repo.save_features(features, user_id=USER_ID)
        print(f"Saved to table  : '{repo.table_name}' (upsert — duplicates are updated)")

    print(f"\n{'Date':<25} {'RMSSD':>7} {'SDNN':>7} {'HR':>6} {'HF_nu':>7} {'LF/HF':>7}")
    print("-" * 65)
    for f in features:
        print(
            f"{str(f.date):<25} {f.rmssd:>7.1f} {f.sdnn:>7.1f} "
            f"{f.mean_hr:>6.1f} {f.hf_nu:>7.2f} {f.lf_hf:>7.2f}"
        )


if __name__ == "__main__":
    feed()
