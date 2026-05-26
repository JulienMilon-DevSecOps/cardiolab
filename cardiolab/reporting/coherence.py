"""Tabular reporting for the cardiac coherence protocol.

Public function:

* :func:`table_coherence_history` — multi-session coherence history with
  score gradient and category highlighting (low / moderate / high).
"""

from __future__ import annotations

import pandas as pd

from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.reporting._core import (
    _COH_CAT_COLORS,
    caption,
    fmt_float,
    gradient_bad,
    gradient_good,
    highlight_category,
)

# Coherence thresholds (McCraty / HeartMath standard)
_COH_HIGH = 60.0
_COH_MODERATE = 40.0


def _coherence_category(score: float) -> str:
    """Return ``"high"``, ``"moderate"``, or ``"low"`` for a coherence score."""
    if score >= _COH_HIGH:
        return "high"
    if score >= _COH_MODERATE:
        return "moderate"
    return "low"


def table_coherence_history(
    results: list[CoherenceResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique cohérence cardiaque — vert ≥ 60 % · rouge < 40 %",
) -> pd.Styler:
    """Build a multi-session cardiac coherence history table.

    One row per session.  The coherence score gradient runs from red (poor
    resonance, < 40 %) to green (good coherence, ≥ 60 %).  A derived
    ``category`` column (``low`` / ``moderate`` / ``high``) is appended and
    colour-highlighted since :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`
    does not expose a category field directly.

    Args:
        results: List of :class:`~cardiolab.protocols.cardiac_coherence.CoherenceResult`
            in chronological order.
        dates: Session labels. Falls back to the result ``date`` attribute or
            ``"Session N"`` when ``None``.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``results`` is not a list or contains wrong types.
        ValueError: If ``results`` is empty or ``dates`` length mismatches.

    """
    _validate_list(results, CoherenceResult, "results")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")
    labels = [
        (r.date or (dates[i] if dates else f"Session {i + 1}"))
        for i, r in enumerate(results)
    ]

    float2 = fmt_float(2)
    float1 = fmt_float(1)

    rows = []
    for label, r in zip(labels, results, strict=False):
        rows.append(
            {
                "date": label,
                "coherence_score": r.coherence_score,
                "category": _coherence_category(r.coherence_score),
                "resonance_freq": r.resonance_freq,
                "peak_power": r.peak_power,
                "total_power_resonance": r.total_power_resonance,
                "rmssd": r.rmssd,
                "sdnn": r.sdnn,
                "mean_hr": r.mean_hr,
                "duration": r.duration,
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "coherence_score": float1,
        "resonance_freq": fmt_float(3),
        "peak_power": float2,
        "total_power_resonance": float2,
        "rmssd": float2,
        "sdnn": float2,
        "mean_hr": float1,
        "duration": float1,
    }

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(
        styler, ["coherence_score"], vmin=_COH_MODERATE, vmax=_COH_HIGH
    )
    styler = gradient_good(styler, ["rmssd"])
    styler = gradient_bad(styler, ["mean_hr"])
    styler = highlight_category(styler, "category", _COH_CAT_COLORS)

    return caption(styler, caption_text)


# ── Validation helper ─────────────────────────────────────────────────────────


def _validate_list(lst: list, expected_type: type, name: str) -> None:
    if not isinstance(lst, list):
        raise TypeError(f"{name} must be a list, got {type(lst).__name__}")
    if len(lst) == 0:
        raise ValueError(f"{name} must contain at least one element.")
    for i, item in enumerate(lst):
        if not isinstance(item, expected_type):
            raise TypeError(
                f"{name}[{i}] must be a {expected_type.__name__}, "
                f"got {type(item).__name__}"
            )
