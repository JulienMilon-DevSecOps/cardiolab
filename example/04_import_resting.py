"""Import pipeline — resting protocol.

Converts raw Polar export files (.txt / .csv) into structured JSON session
records ready to be fed into the database (see 02_feed_database.py).

Usage
-----
1. Drop your raw files into:

       cardiolab/datasets/raw/resting/

2. Run this script from the project root:

       python example/04_import_resting.py

Output
------
One JSON file per raw recording, written to:

    cardiolab/datasets/resting/

Each JSON contains:
  - date         — ISO date extracted from the filename
  - device       — "Polar H10"
  - position     — "supine"
  - source_file  — original filename
  - rr_intervals — list of RR intervals in milliseconds
  - duration     — total recording duration in seconds

Already-imported files are skipped (idempotent).
"""

from __future__ import annotations

from cardiolab.scripts.import_rr import import_all

if __name__ == "__main__":
    print("=== cardiolab — import resting raw files ===\n")
    print("Input  : cardiolab/datasets/raw/resting/")
    print("Output : cardiolab/datasets/resting/\n")

    import_all(protocol="resting")

    print("\nDone. Run 02_feed_database.py to push the sessions to PostgreSQL.")
