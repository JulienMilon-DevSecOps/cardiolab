"""Import pipeline — orthostatic protocol.

Converts raw Polar export files (.txt / .csv) of orthostatic recordings into
structured JSON session records ready for analysis with
``cardiolab.protocols.orthostatic``.

Recording requirements
----------------------
The raw file must cover a continuous session with:
  - ≥ 5 min supine (lying down, at rest)
  - a postural change (stand up)
  - ≥ 5 min standing

Total recommended duration: ≥ 12 minutes.

Usage
-----
1. Drop your raw files into:

       cardiolab/datasets/raw/orthostatic/

2. Run this script from the project root:

       python example/05_import_orthostatic.py

Output
------
One JSON file per raw recording, written to:

    cardiolab/datasets/orthostatic/

Each JSON contains:
  - date         — ISO date extracted from the filename
  - device       — "Polar H10"
  - position     — "orthostatic"
  - source_file  — original filename
  - rr_intervals — list of RR intervals in milliseconds (full continuous recording)
  - duration     — total recording duration in seconds

Already-imported files are skipped (idempotent).

Next steps
----------
Load a JSON file and run the protocol::

    import json
    from cardiolab.signals.rr import RRSeries
    from cardiolab.protocols.orthostatic import orthostatic_hrv

    with open("cardiolab/datasets/orthostatic/2026-05-15 08-00-00.json") as f:
        session = json.load(f)

    rr = RRSeries(session["rr_intervals"])
    result = orthostatic_hrv(rr)

    print(result.interpretation)
    print(f"HR response : +{result.hr_response:.1f} bpm")
    print(f"Supine RMSSD: {result.phases.supine.features.rmssd:.1f} ms")
"""

from __future__ import annotations

from cardiolab.scripts.import_rr import import_all

if __name__ == "__main__":
    print("=== cardiolab — import orthostatic raw files ===\n")
    print("Input  : cardiolab/datasets/raw/orthostatic/")
    print("Output : cardiolab/datasets/orthostatic/\n")

    import_all(protocol="orthostatic")

    print("\nDone. Load the JSON files with RRSeries and run orthostatic_hrv().")
