"""Example RR-interval recordings shipped with cardiolab.

Real Polar H10 recordings of the cardiolab author, published voluntarily as
example data (licence CC-BY-4.0, see ``README.md`` in this directory). They
let anyone try every protocol right after ``pip install cardiolab``, with no
database and no sensor::

    from cardiolab.datasets import list_samples, load_sample
    from cardiolab.protocols.resting import resting_hrv

    list_samples("resting")            # → manifest entries (id, date, beats…)
    rr = load_sample("resting", 0)     # → RRSeries, manifest entry in rr.metadata
    features = resting_hrv(rr)
    features.date = rr.metadata["date"]

Files are stored in the raw format users actually export (one RR interval in
ms per line) and read through :func:`cardiolab.sensors_tools.parse_rr_file`,
exactly like your own recordings.

The ``raw/`` sub-directory is the place for **your own** files (ignored by git,
never packaged); it is not part of the sample datasets.
"""

from __future__ import annotations

import json
from functools import cache
from importlib.resources import as_file, files

from cardiolab.sensors_tools.polar import parse_rr_file
from cardiolab.signals.rr import RRSeries

_MANIFEST = "samples.json"


@cache
def _manifest() -> dict:
    """Read and cache the sample manifest shipped with the package."""
    return json.loads(files(__name__).joinpath(_MANIFEST).read_text(encoding="utf-8"))


def list_samples(protocol: str | None = None) -> list[dict]:
    """List the available sample recordings.

    Args:
        protocol: Keep only the samples of this protocol (``"resting"`` or
            ``"orthostatic"``). ``None`` returns every sample.

    Returns:
        Manifest entries sorted by date, one ``dict`` per recording with keys
        ``id``, ``protocol``, ``file``, ``date``, ``recorded_at``, ``device``,
        ``position``, ``beats`` and ``duration_sec``. Copies: modifying them
        does not affect the manifest.

    Raises:
        ValueError: If ``protocol`` has no sample.

    """
    samples = [dict(s) for s in _manifest()["samples"]]
    if protocol is not None:
        samples = [s for s in samples if s["protocol"] == protocol]
        if not samples:
            raise ValueError(f"No sample for protocol {protocol!r}. {_available()}")
    return sorted(samples, key=lambda s: (s["protocol"], s["date"]))


def load_sample(protocol: str = "resting", index: int = 0) -> RRSeries:
    """Load one sample recording as an ``RRSeries``.

    Args:
        protocol: ``"resting"`` (6 recordings, ~5-11 min supine) or
            ``"orthostatic"`` (1 recording, supine → standing, ~10 min).
        index: Position of the recording in ``list_samples(protocol)``
            (chronological order). Negative indices count from the end.

    Returns:
        The raw (uncleaned) RR series. ``metadata`` holds the manifest entry
        plus ``source`` (``"cardiolab sample dataset"``) and ``license``.

    Raises:
        ValueError: If ``protocol`` has no sample.
        IndexError: If ``index`` is out of range.

    """
    samples = list_samples(protocol)
    try:
        sample = samples[index]
    except IndexError:
        raise IndexError(
            f"Sample index {index} out of range for protocol {protocol!r} "
            f"({len(samples)} sample(s))."
        ) from None

    with as_file(files(__name__).joinpath(sample["file"])) as path:
        parsed = parse_rr_file(path)

    metadata = {
        **sample,
        "source": "cardiolab sample dataset",
        "license": _manifest()["license"],
    }
    return RRSeries(parsed["rr_intervals"], metadata=metadata)


def _available() -> str:
    """Describe the available protocols for error messages."""
    protocols = sorted({s["protocol"] for s in _manifest()["samples"]})
    return f"Available: {', '.join(protocols)}."


__all__ = ["list_samples", "load_sample"]
