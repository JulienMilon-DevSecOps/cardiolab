"""Tabular reporting for the Heart Rate Recovery protocol.

Public function:

* :func:`table_hrr_history` — multi-session HRR history with clinical
  categories highlighted and colour gradients on recovery speed indicators.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.protocols.hrr import HRRResult
from cardiolab.reporting._core import (
    _HRR_CAT_COLORS,
    caption,
    fmt_float,
    fmt_nan,
    gradient_bad,
    gradient_good,
    highlight_category,
)


def table_hrr_history(
    results: list[HRRResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique HRR — récupération cardiaque post-effort",
) -> pd.Styler:
    """Build a multi-session Heart Rate Recovery history table.

    One row per session.  Key indicators are colour-coded: higher HRR values
    (faster vagal reactivation) are shown in green, clinical categories are
    highlighted according to the Cole et al. 1999 classification.

    Args:
        results: List of :class:`~cardiolab.protocols.hrr.HRRResult`
            in chronological order.
        dates: Session labels. Falls back to ``"Session N"`` when ``None``.
            Ignored when :attr:`~cardiolab.protocols.hrr.HRRResult.date` is
            already set on each result.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``results`` is not a list or contains wrong types.
        ValueError: If ``results`` is empty or ``dates`` length mismatches.

    """
    _validate_list(results, HRRResult, "results")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")
    labels = [
        (r.date or (dates[i] if dates else f"Session {i + 1}"))
        for i, r in enumerate(results)
    ]

    nan_fmt = fmt_nan(1)
    float2 = fmt_float(2)
    float1 = fmt_float(1)

    rows = []
    for label, r in zip(labels, results, strict=False):
        rows.append(
            {
                "date": label,
                "hr_peak": r.hr_peak,
                "hr_at_60s": r.hr_at_60s,
                "hrr_60": r.hrr_60,
                "hrr_60_category": r.hrr_60_category,
                "hr_at_120s": r.hr_at_120s,
                "hrr_120": r.hrr_120,
                "hrr_120_category": r.hrr_120_category,
                "duration": r.duration,
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "hr_peak": float1,
        "hr_at_60s": float1,
        "hrr_60": float1,
        "hr_at_120s": nan_fmt,
        "hrr_120": nan_fmt,
        "duration": float2,
    }

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, ["hrr_60", "hrr_120"], vmin=0, vmax=40)
    styler = gradient_bad(styler, ["hr_peak"])
    styler = highlight_category(styler, "hrr_60_category", _HRR_CAT_COLORS)
    styler = highlight_category(styler, "hrr_120_category", _HRR_CAT_COLORS)

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
