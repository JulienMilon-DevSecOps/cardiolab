"""Tabular reporting for the cardiac drift protocol.

Public function:

* :func:`table_drift_history` — multi-session drift history with drift rate,
  magnitude, R² and clinical category highlighted by colour.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.reporting._core import (
    _DRIFT_CAT_COLORS,
    apply_labels,
    caption,
    fmt_float,
    gradient_bad,
    gradient_good,
    highlight_category,
)


def table_drift_history(
    results: list[DriftResult],
    dates: list[str] | None = None,
    labels: dict[str, str] | None = None,
    caption_text: str = "Cardiac drift history — green = stable · red = strong drift",
) -> pd.Styler:
    """Build a multi-session cardiac drift history table.

    One row per session.  Drift rate and magnitude are colour-coded: lower
    values (less drift) are shown in green.  The clinical category cell is
    highlighted according to the standard drift classification.

    Args:
        results: List of :class:`~cardiolab.protocols.cardiac_drift.DriftResult`
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
    _validate_list(results, DriftResult, "results")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")
    date_labels = [
        (r.date or (dates[i] if dates else f"Session {i + 1}"))
        for i, r in enumerate(results)
    ]

    float2 = fmt_float(2)
    float1 = fmt_float(1)

    rows = []
    for date_label, r in zip(date_labels, results, strict=False):
        rows.append(
            {
                "date": date_label,
                "drift_rate": r.drift_rate,
                "drift_magnitude": r.drift_magnitude,
                "r_squared": r.r_squared,
                "initial_hr": r.initial_hr,
                "final_hr": r.final_hr,
                "n_windows": r.n_windows,
                "duration": r.duration,
                "interpretation": r.interpretation,
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "drift_rate": float2,
        "drift_magnitude": float1,
        "r_squared": float2,
        "initial_hr": float1,
        "final_hr": float1,
        "duration": float1,
    }

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_bad(styler, ["drift_rate"], vmin=0, vmax=3)
    styler = gradient_bad(styler, ["drift_magnitude"], vmin=0, vmax=15)
    styler = gradient_good(styler, ["r_squared"], vmin=0, vmax=1)
    styler = highlight_category(styler, "interpretation", _DRIFT_CAT_COLORS)
    styler = apply_labels(styler, labels)

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
