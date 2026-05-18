"""Export utilities — serialise HRV data to CSV and JSON.

All functions use only the Python standard library (``csv``, ``json``,
``pathlib``) and impose no dependency on pandas. The ``to_dataframe()``
methods on the data classes are the entry point for pandas-based workflows.

Functions
---------
features_to_csv
    Export one or more ``HRVFeatures`` sessions to a CSV file.
features_to_json
    Export one or more ``HRVFeatures`` sessions to a JSON file.
orthostatic_to_csv
    Export an ``OrthostaticResult`` to a wide-format CSV file.
orthostatic_to_json
    Export an ``OrthostaticResult`` to a nested JSON file.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardiolab.protocols.orthostatic import OrthostaticResult
    from cardiolab.protocols.resting import HRVFeatures

StrPath = str | Path


# ======================
# INTERNAL HELPERS
# ======================


def _as_list(features: HRVFeatures | list[HRVFeatures]) -> list[HRVFeatures]:
    """Return *features* wrapped in a list if it is a single instance."""
    from cardiolab.protocols.resting import HRVFeatures as _HRVFeatures

    if isinstance(features, _HRVFeatures):
        return [features]
    return list(features)


def _sanitise(value: object) -> object:
    """Replace NaN / ±Inf with ``None`` for JSON-safe serialisation."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _sanitise_dict(d: dict) -> dict:
    """Recursively apply :func:`_sanitise` to all scalar values in *d*."""
    out: dict = {}
    for key, val in d.items():
        if isinstance(val, dict):
            out[key] = _sanitise_dict(val)
        else:
            out[key] = _sanitise(val)
    return out


def _write_csv(path: StrPath, rows: list[dict]) -> None:
    """Write *rows* (list of flat dicts with identical keys) to *path*."""
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Replace NaN / Inf so the CSV is parseable by downstream tools.
            writer.writerow({k: _sanitise(v) for k, v in row.items()})


# ======================
# PUBLIC API
# ======================


def features_to_csv(
    features: HRVFeatures | list[HRVFeatures],
    path: StrPath,
) -> None:
    """Export one or more ``HRVFeatures`` sessions to a CSV file.

    Each session becomes one row. Column order follows ``HRVFeatures.to_dict``
    (i.e. the same order as the dataclass field declaration). NaN / ±Inf
    values are written as empty cells.

    Args:
        features: A single ``HRVFeatures`` instance or an ordered list of
            sessions (chronological order is recommended).
        path: Destination file path. The file is created or overwritten.

    Example::

        from cardiolab.io import features_to_csv
        features_to_csv(session, "session.csv")
        features_to_csv(baseline.history, "history.csv")

    """
    rows = [f.to_dict() for f in _as_list(features)]
    _write_csv(path, rows)


def features_to_json(
    features: HRVFeatures | list[HRVFeatures],
    path: StrPath,
    indent: int = 2,
) -> None:
    """Export one or more ``HRVFeatures`` sessions to a JSON file.

    The output is a JSON array even when a single session is passed.
    NaN / ±Inf values are serialised as ``null``.

    Args:
        features: A single ``HRVFeatures`` instance or an ordered list.
        path: Destination file path. Created or overwritten.
        indent: JSON indentation level. Defaults to 2.

    Example::

        from cardiolab.io import features_to_json
        features_to_json(baseline.history, "history.json")

    """
    rows = [_sanitise_dict(f.to_dict()) for f in _as_list(features)]
    Path(path).write_text(json.dumps(rows, indent=indent), encoding="utf-8")


def orthostatic_to_json(
    result: OrthostaticResult,
    path: StrPath,
    indent: int = 2,
) -> None:
    """Export an ``OrthostaticResult`` to a nested JSON file.

    The full structure produced by ``OrthostaticResult.to_dict()`` is
    preserved (phases → features). NaN / ±Inf values are serialised as
    ``null``.

    Args:
        result: The orthostatic result to export.
        path: Destination file path. Created or overwritten.
        indent: JSON indentation level. Defaults to 2.

    Example::

        from cardiolab.io import orthostatic_to_json
        orthostatic_to_json(result, "ortho_2026-05-18.json")

    """
    data = _sanitise_dict(result.to_dict())
    Path(path).write_text(json.dumps(data, indent=indent), encoding="utf-8")


def orthostatic_to_csv(
    result: OrthostaticResult,
    path: StrPath,
) -> None:
    """Export an ``OrthostaticResult`` to a wide-format CSV file.

    Uses ``OrthostaticResult.to_flat_dict()`` to flatten all phases into a
    single row with prefixed column names (``supine_``, ``transition_``,
    ``standing_``). The resulting CSV has one data row — append multiple
    rows to build a longitudinal database.

    Args:
        result: The orthostatic result to export.
        path: Destination file path. Created or overwritten.

    Example::

        from cardiolab.io import orthostatic_to_csv
        orthostatic_to_csv(result, "ortho_2026-05-18.csv")

    """
    _write_csv(path, [result.to_flat_dict()])
