"""Compute HRV features from JSON session files and persist them to the database.

Run this script after each new recording session (or in batch to import all
existing sessions at once). The upsert strategy means re-running on the same
files is safe: existing rows are updated rather than duplicated.

Workflow
--------
1. Read all ``.json`` files from ``cardiolab/datasets/resting/``.
2. Build an ``RRSeries`` from each file's ``rr_intervals`` array.
3. Compute the full ``HRVFeatures`` set via ``resting_hrv()``.
4. Persist every session to the database under your ``USER_ID``.

Prerequisites
-------------
* ``01_setup_database.py`` must have been run at least once.
* ``.env`` file with ``DB_*`` variables and a stable ``USER_ID`` (UUID).

Usage
-----
Run from the project root::

    python example/02_feed_database.py

"""

from __future__ import annotations

import glob
import json
import os
import uuid

from dotenv import load_dotenv

from cardiolab.database.repository import HRVRepository
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.rr import RRSeries

load_dotenv()

# ---------------------------------------------------------------------------
# USER IDENTITY
# ---------------------------------------------------------------------------
# USER_ID is a stable UUID that uniquely identifies you in the database.
# Generate it once with: python3 -c "import uuid; print(uuid.uuid4())"
# then store it in .env as USER_ID=<your-uuid>.
#
# If USER_ID is absent from the environment this script creates a new one
# and prints it so you can copy it into .env.
# ---------------------------------------------------------------------------

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
    USER_ID = str(uuid.UUID(_raw_user_id))  # normalises format to 8-4-4-4-12


# ---------------------------------------------------------------------------
# JSON → HRVFeatures
# ---------------------------------------------------------------------------

def load_features_from_json(
    path: str = "cardiolab/datasets/resting/*.json",
) -> list[HRVFeatures]:
    """Load resting-protocol JSON files and compute HRV features for each.

    Args:
        path: Glob pattern pointing to the session JSON files.

    Returns:
        List of ``HRVFeatures``, one per file, with ``date`` set from the JSON.

    """
    files = sorted(glob.glob(path))

    if not files:
        print(f"No JSON files found at: {path}")
        return []

    features: list[HRVFeatures] = []

    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)

        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)

        session = HRVFeatures(
            date=data["date"],
            rmssd=result.rmssd,
            ln_rmssd=result.ln_rmssd,
            sdnn=result.sdnn,
            pnn50=result.pnn50,
            mean_hr=result.mean_hr,
            vlf=result.vlf,
            lf=result.lf,
            hf=result.hf,
            lf_hf=result.lf_hf,
            hf_pct=result.hf_pct,
            lf_nu=result.lf_nu,
            hf_nu=result.hf_nu,
            duration=result.duration,
        )

        features.append(session)

    return features


# ---------------------------------------------------------------------------
# DISPLAY
# ---------------------------------------------------------------------------

def display_features(features: list[HRVFeatures]) -> None:
    """Print a compact summary of each session."""
    print(f"\n{'Date':<25} {'RMSSD':>7} {'SDNN':>7} {'HR':>6} {'HF_nu':>7} {'LF/HF':>7}")
    print("-" * 65)
    for f in features:
        print(
            f"{str(f.date):<25} "
            f"{f.rmssd:>7.1f} "
            f"{f.sdnn:>7.1f} "
            f"{f.mean_hr:>6.1f} "
            f"{f.hf_nu:>7.2f} "
            f"{f.lf_hf:>7.2f}"
        )


# ---------------------------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------------------------

def feed(path: str = "cardiolab/datasets/resting/*.json") -> None:
    """Full feed pipeline: compute features, persist to DB, print summary."""
    print("=== cardiolab — feed database ===\n")
    print(f"User ID : {USER_ID}")

    features = load_features_from_json(path)

    if not features:
        return

    print(f"Sessions found : {len(features)}")

    with HRVRepository.from_env() as repo:
        repo.save_features(features, user_id=USER_ID)
        print(f"Saved to table  : '{repo.table_name}' (upsert — duplicates are updated)")

    display_features(features)


if __name__ == "__main__":
    feed()
