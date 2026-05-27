"""Tabular reporting for the orthostatic HRV protocol.

Two public functions:

* :func:`table_orthostatic_comparison` — side-by-side supine vs standing
  comparison with delta columns, one row per session.
* :func:`table_orthostatic_history` — condensed history showing the key
  autonomic response indicators per session.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.protocols.orthostatic import OrthostaticResult
from cardiolab.reporting._core import (
    _ORTHO_CAT_COLORS,
    caption,
    fmt_float,
    fmt_nan,
    gradient_bad,
    gradient_good,
    highlight_category,
)

# ── Phase metrics included in the comparison table ────────────────────────────

_PHASE_METRICS: list[str] = [
    "rmssd",
    "mean_hr",
    "sd1",
    "sd2",
    "sd_ratio",
    "dfa_alpha1",
    "hf_nu",
    "apen",
    "sampen",
]

_NAN_SUFFIXES: tuple[str, ...] = ("dfa_alpha1", "apen", "sampen")


# ── Public functions ──────────────────────────────────────────────────────────


def table_orthostatic_comparison(
    results: list[OrthostaticResult],
    dates: list[str] | None = None,
    caption_text: str = "Comparaison allongé / debout — rouge = bas · vert = élevé",
) -> pd.Styler:
    """Build a supine vs standing comparison table.

    Each row represents one session.  For each phase metric the supine
    (``supine_*``) and standing (``standing_*``) values are shown side by
    side.  Delta autonomic response indicators (HR response, HF%, HF/FC)
    are appended on the right.

    Args:
        results: List of :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
            in chronological order.
        dates: Session labels. Falls back to ``"Session N"`` when ``None``.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``results`` is not a list or contains wrong types.
        ValueError: If ``results`` is empty or ``dates`` length mismatches.

    """
    _validate_list(results, OrthostaticResult, "results")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")
    labels = dates or [f"Session {i + 1}" for i in range(n)]

    rows = []
    for label, r in zip(labels, results, strict=False):
        row: dict[str, object] = {"date": label}
        p = r.phases
        for col in _PHASE_METRICS:
            row[f"supine_{col}"] = getattr(p.supine.features, col, float("nan"))
            row[f"standing_{col}"] = getattr(p.standing.features, col, float("nan"))
        row["hr_response"] = r.hr_response
        row["lf_hf_change"] = r.lf_hf_ratio_change
        row["hf_response_pct"] = r.hf_response_pct
        row["hf_hr_pct_change"] = r.hf_hr_pct_change
        row["interpretation"] = r.interpretation
        rows.append(row)

    df = pd.DataFrame(rows)

    # Format spec: nan-safe for DFA/Apen/SampEn columns
    nan_fmt = fmt_nan(3)
    float_fmt = fmt_float(2)

    def _col_fmt(col: str) -> object:
        if any(col.endswith(s) for s in _NAN_SUFFIXES):
            return nan_fmt
        if col in ("lf_hf_change",):
            return fmt_float(2)
        return float_fmt

    fmt = {c: _col_fmt(c) for c in df.select_dtypes("float").columns}

    styler = df.style.format(fmt, na_rep="n/a")

    # Gradients: supine RMSSD, SD1, HF_nu → green = good
    supine_good = [f"supine_{m}" for m in ("rmssd", "sd1", "sd2", "hf_nu")]
    standing_good = [f"standing_{m}" for m in ("rmssd", "sd1", "sd2", "hf_nu")]
    styler = gradient_good(styler, supine_good)
    styler = gradient_good(styler, standing_good)

    # HR response: lower is better (orthostatic tachycardia)
    styler = gradient_bad(styler, ["hr_response"], vmin=0, vmax=30)
    # HF response %: more negative = more vagal withdrawal (normal) → depends on sign
    # lf_hf_change: > 1 = sympathetic activation (expected at standing)

    # Category colouring
    styler = highlight_category(styler, "interpretation", _ORTHO_CAT_COLORS)

    return caption(styler, caption_text)


def table_orthostatic_history(
    results: list,
    dates: list[str] | None = None,
    caption_text: str = "Historique orthostatique — réponse autonome par session",
) -> pd.Styler:
    """Build a condensed multi-session orthostatic history table.

    Shows key autonomic response indicators per session (HR response,
    HF% change, HF/FC% change, LF/HF ratio change, interpretation).

    Args:
        results: List of orthostatic result objects in chronological order.
            Accepts both :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
            (live protocol output) and
            :class:`~cardiolab.database.repository.OrthostaticRecord`
            (database read-back). The two types expose the same response-metric
            attributes; ``OrthostaticRecord`` additionally exposes
            ``to_reporting_row()`` for convenience.
        dates: Session labels. Falls back to ``r.date`` or ``"Session N"``.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        ValueError: If ``results`` is empty or ``dates`` length mismatches.

    """
    if not isinstance(results, list):
        raise TypeError(f"results must be a list, got {type(results).__name__}")
    if len(results) == 0:
        raise ValueError("results must contain at least one element.")
    n = len(results)
    if dates is not None and len(dates) != n:
        raise ValueError(f"dates length ({len(dates)}) must match results length ({n})")

    rows = []
    for i, r in enumerate(results):
        # Duck-typing: OrthostaticRecord exposes to_reporting_row()
        if hasattr(r, "to_reporting_row"):
            row = r.to_reporting_row()
            row["date"] = (
                (dates[i] if dates else None) or row.get("date") or f"Session {i + 1}"
            )
        else:
            # OrthostaticResult — access via phases
            p = r.phases
            label = (
                (dates[i] if dates else None)
                or getattr(r, "date", None)
                or f"Session {i + 1}"
            )
            row = {
                "date": label,
                "supine_rmssd": p.supine.features.rmssd,
                "standing_rmssd": p.standing.features.rmssd,
                "supine_hr": p.supine.features.mean_hr,
                "standing_hr": p.standing.features.mean_hr,
                "hr_response": r.hr_response,
                "lf_hf_change": r.lf_hf_ratio_change,
                "hf_response_pct": r.hf_response_pct,
                "hf_hr_pct_change": r.hf_hr_pct_change,
                "interpretation": r.interpretation,
            }
        rows.append(row)

    df = pd.DataFrame(rows)

    fmt = {c: fmt_float(2) for c in df.select_dtypes("float").columns}

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, ["supine_rmssd", "standing_rmssd"])
    styler = gradient_bad(styler, ["supine_hr", "standing_hr"])
    styler = gradient_bad(styler, ["hr_response"], vmin=0, vmax=30)
    styler = highlight_category(styler, "interpretation", _ORTHO_CAT_COLORS)

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
