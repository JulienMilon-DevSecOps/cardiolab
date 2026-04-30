"""Functions to parse data export files from polar sensors."""

from __future__ import annotations

import csv
from pathlib import Path

# ======================
# PUBLIC API
# ======================

def parse_rr_file(filepath: str | Path) -> dict:
    """Detect format and calls appropriate parser.
    
    FR :
    Parse automatiquement un fichier RR (CSV ou TXT).
    Détecte le format et appelle le bon parser.
    EN :
    Automatically parses an RR file (CSV or TXT).
    Detects format and calls appropriate parser.
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
    """Parse a CSV file with RR intervals.
    
    FR :
    Parse un CSV Polar ou similaire avec une colonne RR.
    EN :
    Parses a CSV file with RR intervals.
    """
    rr_intervals: list[float] = []

    with open(filepath) as f:
        reader = csv.DictReader(f)

        # Détection colonne RR
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
# TXT PARSER (Elite HRV)
# ======================

def _parse_txt(filepath: Path) -> dict:
    """Parse a TXT file with one column of RR intervals.
    
    FR :
    Parse un fichier TXT contenant une colonne d'intervalles RR.
    Format attendu :
    800
    810
    790
    ...
    EN :
    Parses a TXT file with one column of RR intervals.
    Format :
    800
    810
    790
    ...
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
                # ignore header ou lignes invalides
                continue

    if not rr_intervals:
        raise ValueError("No valid RR intervals found in TXT file")

    return _build_output(filepath, rr_intervals)


# ======================
# COMMON OUTPUT
# ======================

def _build_output(filepath: Path, rr_intervals: list[float]) -> dict:
    """Build a standardized output.
    
    FR :
    Construit une sortie standardisée.
    EN :
    Builds a standardized output.
    """
    return {
        "source": filepath.name,
        "format": filepath.suffix.lower(),
        "rr_intervals": rr_intervals,
        "count": len(rr_intervals),
        "duration_sec": sum(rr_intervals) / 1000.0,
    }