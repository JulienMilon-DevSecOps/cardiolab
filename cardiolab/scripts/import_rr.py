from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cardiolab.sensors_tools.polar import parse_rr_file

RAW_DIR = Path("cardiolab/datasets/raw")



def import_all(output_dir = "cardiolab/datasets/resting"):
    """
    FR :
    Importe tous les fichiers RR (txt/csv) depuis datasets/raw
    et les convertit en JSON dans datasets/resting.

    EN :
    Imports all RR files (txt/csv) from datasets/raw
    and converts them into JSON in datasets/resting.
    """

    OUTPUT_DIR = Path(output_dir)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = list(RAW_DIR.glob("*"))

    if not files:
        print("No files found in datasets/raw")
        return

    for file in files:
        try:
            data = parse_rr_file(file)

            # ======================
            # DATE
            # ======================

            # tente d'extraire depuis nom fichier sinon maintenant
            date_str = _extract_date(file.name)

            output = {
                "date": date_str,
                "device": "Polar H10",
                "position": "supine",
                "source_file": file.name,
                "rr_intervals": data["rr_intervals"],
                "duration": data["duration_sec"],
            }

            out_path = OUTPUT_DIR / f"{date_str}.json"

            # ======================
            # DUPLICATION PROTECTION
            # ======================

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
    """
    FR :
    Essaie d'extraire une date depuis le nom du fichier.

    EN :
    Attempts to extract a date from filename.
    """

    # ex: 2026-04-24.txt
    try:
        return filename.split(".")[0]
    except Exception:
        return datetime.today().date().isoformat()
