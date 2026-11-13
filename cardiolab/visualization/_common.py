"""Shared helpers of the plotting modules: colours, argument checks, labels."""

from __future__ import annotations

from collections.abc import Sequence

from cardiolab.labels import LABELS_EN, lbl
from cardiolab.signals.rr import RRSeries

DARK = "#2c3e50"
"""Titles, text and neutral lines."""

GRAY = "#95a5a6"
"""Secondary lines, references, missing values."""

# Letters whose spoken name starts with a vowel sound (« an HRV… », « an RR… »).
_VOWEL_SOUND_LETTERS = frozenset("AEFHILMNORSX")


def _article(name: str) -> str:
    """Return « a » or « an » before a class name (``HRRResult`` → « an »)."""
    if name[:2].isupper():  # acronym: read letter by letter
        return "an" if name[0] in _VOWEL_SOUND_LETTERS else "a"
    return "an" if name[0].upper() in "AEIOU" else "a"


def check_type(obj: object, cls: type, name: str) -> None:
    """Raise unless ``obj`` is an instance of ``cls``.

    Raises:
        TypeError: ``"<name> must be a <Class>, got <type>"``.

    """
    if not isinstance(obj, cls):
        raise TypeError(
            f"{name} must be {_article(cls.__name__)} {cls.__name__}, "
            f"got {type(obj).__name__}"
        )


def check_list(items: object, cls: type, name: str) -> None:
    """Raise unless ``items`` is a non-empty list of ``cls``.

    Raises:
        TypeError: Not a list, or an item of another type
            (``"<name>[i] must be a <Class>, got <type>"``).
        ValueError: Empty list.

    """
    if not isinstance(items, list):
        raise TypeError(f"{name} must be a list, got {type(items).__name__}")
    if not items:
        raise ValueError(f"{name} must contain at least one {cls.__name__}.")
    for i, item in enumerate(items):
        check_type(item, cls, f"{name}[{i}]")


def check_rr(rr: object, min_intervals: int) -> None:
    """Raise unless ``rr`` is an :class:`RRSeries` with enough intervals.

    Raises:
        TypeError: Not an ``RRSeries``.
        ValueError: Fewer than ``min_intervals`` intervals.

    """
    check_type(rr, RRSeries, "rr")
    if len(rr.intervals) < min_intervals:
        raise ValueError(
            f"rr must have at least {min_intervals} intervals, got {len(rr.intervals)}"
        )


def text(labels: dict[str, str] | None, key: str) -> str:
    """Label of ``key`` from ``labels``, the English label by default."""
    return lbl(labels, key, LABELS_EN[key])


def default_labels(items: Sequence) -> list[str]:
    """Session dates as labels, ``"Session N"`` when an item has no date."""
    return [
        str(item.date) if item.date else f"Session {i + 1}"
        for i, item in enumerate(items)
    ]
