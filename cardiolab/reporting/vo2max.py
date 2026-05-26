"""Tabular reporting for the VO2max estimation protocol.

Two public functions:

* :func:`table_vo2max_history` — multi-session history with all three model
  estimates and fitness category highlighted by ACSM zone.
* :func:`table_vo2max_session` — single-session detail with model breakdown,
  input values and fitness category.
"""

from __future__ import annotations

import math

import pandas as pd

from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.reporting._core import (
    _VO2_CAT_COLORS,
    caption,
    fmt_float,
    fmt_nan,
    gradient_good,
    highlight_category,
)


def table_vo2max_history(
    results: list[VO2maxResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique VO2max — vert = élevé · ACSM 2022",
) -> pd.Styler:
    """Build a multi-session VO2max history table.

    One row per session.  All three model estimates are shown side by side.
    ``vo2max_uth`` displays ``n/a`` when ``hr_max`` was not provided.
    The ``fitness_category`` cell is colour-highlighted by ACSM zone.

    Args:
        results: List of :class:`~cardiolab.protocols.vo2max.VO2maxResult`
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
    _validate_list(results, VO2maxResult, "results")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")
    labels = [
        (r.date or (dates[i] if dates else f"Session {i + 1}"))
        for i, r in enumerate(results)
    ]

    nan_fmt = fmt_nan(1)
    float1 = fmt_float(1)
    float2 = fmt_float(2)

    rows = []
    for label, r in zip(labels, results, strict=False):
        rows.append(
            {
                "date": label,
                "vo2max_uth": r.vo2max_uth,
                "vo2max_esco_flatt": r.vo2max_esco_flatt,
                "vo2max_ln_rmssd": r.vo2max_ln_rmssd,
                "hr_rest": r.hr_rest,
                "hr_max": r.hr_max,
                "rmssd_used": r.rmssd_used,
                "ln_rmssd_used": r.ln_rmssd_used,
                "fitness_category": r.fitness_category,
            }
        )

    df = pd.DataFrame(rows)

    fmt: dict = {
        "vo2max_uth": nan_fmt,
        "vo2max_esco_flatt": float1,
        "vo2max_ln_rmssd": float1,
        "hr_rest": float1,
        "hr_max": nan_fmt,
        "rmssd_used": float2,
        "ln_rmssd_used": float2,
    }

    vo2_cols = ["vo2max_esco_flatt", "vo2max_ln_rmssd"]
    if any(not math.isnan(r.vo2max_uth) for r in results):
        vo2_cols.insert(0, "vo2max_uth")

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, vo2_cols, vmin=20, vmax=65)
    styler = highlight_category(styler, "fitness_category", _VO2_CAT_COLORS)

    return caption(styler, caption_text)


def table_vo2max_session(
    result: VO2maxResult,
    caption_text: str | None = None,
) -> pd.Styler:
    """Build a single-session VO2max detail table.

    Displays all three model estimates, input physiological values, and the
    ACSM fitness category.  Each row is one indicator; the category cell is
    colour-highlighted.

    Args:
        result: :class:`~cardiolab.protocols.vo2max.VO2maxResult` for one
            session.
        caption_text: Caption shown below the table. Defaults to the session
            date when available.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``result`` is not a VO2maxResult.

    """
    if not isinstance(result, VO2maxResult):
        raise TypeError(f"result must be a VO2maxResult, got {type(result).__name__}")

    nan_fmt = fmt_nan(1)

    uth_val = nan_fmt(result.vo2max_uth)
    hr_max_val = nan_fmt(result.hr_max)

    rows = [
        # Model estimates
        ("VO2max Uth (mL/kg/min)", uth_val, "Model"),
        ("VO2max Esco-Flatt (mL/kg/min)", f"{result.vo2max_esco_flatt:.1f}", "Model"),
        ("VO2max ln-RMSSD (mL/kg/min)", f"{result.vo2max_ln_rmssd:.1f}", "Model"),
        # Inputs
        ("HR repos (bpm)", f"{result.hr_rest:.1f}", "Inputs"),
        ("HR max (bpm)", hr_max_val, "Inputs"),
        ("RMSSD utilisé (ms)", f"{result.rmssd_used:.2f}", "Inputs"),
        ("ln(RMSSD) utilisé", f"{result.ln_rmssd_used:.3f}", "Inputs"),
        # Result
        ("Catégorie fitness", result.fitness_category, "Result"),
    ]

    df = pd.DataFrame(rows, columns=["Indicateur", "Valeur", "Groupe"])
    df = df.set_index("Indicateur")

    def _colour_cat(val: str) -> str:
        key = str(val).lower().replace(" ", "_")
        bg = _VO2_CAT_COLORS.get(key, "")
        return f"background-color: {bg}" if bg else ""

    styler = df.style.map(_colour_cat, subset=["Valeur"])

    cap = caption_text or (
        f"VO2max — Session {result.date}" if result.date else "VO2max — Session detail"
    )
    return styler.set_caption(cap)


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
