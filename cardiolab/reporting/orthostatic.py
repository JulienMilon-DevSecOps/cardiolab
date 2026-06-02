"""Tabular reporting for the orthostatic HRV protocol.

Two public functions:

* :func:`table_orthostatic_comparison` — three-phase comparison (supine /
  transition / standing) with full HRV indicators and autonomic response
  deltas, one row per session.
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


# Response metrics shown in the comparison table (right-hand group)
_RESPONSE_METRICS: list[str] = [
    "hr_response",
    "hf_response_pct",
    "hf_hr_pct_change",
    "lf_hr_pct_change",
    "delta_rmssd",
    "lf_hf_change",
    "interpretation",
]

# Mapping flat column name → (phase_group, short_name) for MultiIndex display
_PHASE_PREFIX: list[tuple[str, str]] = [
    ("supine_", "Supine"),
    ("transition_", "Transition"),
    ("standing_", "Standing"),
]


def _to_multiindex_col(col: str) -> tuple[str, str]:
    """Map a flat column name to a (phase_group, short_name) tuple."""
    for prefix, group in _PHASE_PREFIX:
        if col.startswith(prefix):
            return (group, col[len(prefix):])
    return ("Autonomic response", col)


def table_orthostatic_comparison(
    results: list,
    dates: list[str] | None = None,
    cols: list[str] | None = None,
    caption_text: str = "Supine / Transition / Standing — red = low · green = high",
) -> pd.Styler:
    """Build a three-phase comparison table: supine, transition, and standing.

    Columns are grouped by phase using a MultiIndex header so each phase
    can be read as a standalone resting HRV panel.

    Args:
        results: List of orthostatic result objects in chronological order.
            Accepts both :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
            (live protocol output) and
            :class:`~cardiolab.database.repository.OrthostaticRecord`
            (database read-back).
        dates: Session labels. Falls back to ``"Session N"`` when ``None``.
        cols: Subset of flat column names to display (e.g. ``"supine_rmssd"``,
            ``"hr_response"``). Defaults to all metrics. Unknown names raise
            :class:`ValueError`.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``results`` is not a list.
        ValueError: If ``results`` is empty, ``dates`` length mismatches, or
            ``cols`` contains unknown column names.

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
        label = (dates[i] if dates else None) or getattr(r, "date", None) or f"Session {i + 1}"
        row: dict[str, object] = {"date": label}

        # Duck-type OrthostaticResult (has .phases) or OrthostaticRecord (flat attrs)
        if hasattr(r, "phases"):
            p = r.phases
            sup_f, trans_f, sta_f = p.supine.features, p.transition.features, p.standing.features
            trans_delta_hr: float = p.transition.delta_hr
            trans_peak_hr: float = p.transition.peak_hr
        else:
            sup_f, trans_f, sta_f = r.supine, r.transition_features, r.standing
            trans_delta_hr = r.transition_delta_hr
            trans_peak_hr = r.transition_peak_hr

        # Supine — all metrics
        for col in _PHASE_METRICS:
            row[f"supine_{col}"] = getattr(sup_f, col, float("nan"))
        # Transition — all metrics + HR dynamics
        for col in _PHASE_METRICS:
            row[f"transition_{col}"] = getattr(trans_f, col, float("nan"))
        row["transition_delta_hr"] = trans_delta_hr
        row["transition_peak_hr"] = trans_peak_hr
        # Standing — all metrics
        for col in _PHASE_METRICS:
            row[f"standing_{col}"] = getattr(sta_f, col, float("nan"))
        # Autonomic response metrics
        row["hr_response"] = r.hr_response
        row["hf_response_pct"] = r.hf_response_pct
        row["hf_hr_pct_change"] = r.hf_hr_pct_change
        row["lf_hr_pct_change"] = r.lf_hr_pct_change
        row["delta_rmssd"] = r.delta_rmssd
        row["lf_hf_change"] = r.lf_hf_ratio_change
        row["interpretation"] = r.interpretation
        rows.append(row)

    df_flat = pd.DataFrame(rows).set_index("date")

    # Column filtering on flat names before MultiIndex conversion
    if cols is not None:
        unknown = set(cols) - set(df_flat.columns)
        if unknown:
            raise ValueError(f"Unknown column(s): {sorted(unknown)}")
        df_flat = df_flat[[c for c in cols if c in df_flat.columns]]

    # Convert to MultiIndex so styles are applied with the final column structure
    mi = pd.MultiIndex.from_tuples([_to_multiindex_col(c) for c in df_flat.columns])
    df = df_flat.copy()
    df.columns = mi

    # Format spec: nan-safe for DFA/Apen/SampEn columns (keyed by short name = tuple[1])
    nan_fmt = fmt_nan(3)
    float_fmt = fmt_float(2)

    def _mi_fmt(col: tuple) -> object:
        return nan_fmt if any(col[1].endswith(s) for s in _NAN_SUFFIXES) else float_fmt

    fmt = {c: _mi_fmt(c) for c in df.select_dtypes("float").columns}

    styler = df.style.format(fmt, na_rep="n/a")

    # Gradients — use MultiIndex tuples directly
    supine_good = [c for c in df.columns if c[0] == "Supine" and c[1] in ("rmssd", "sd1", "sd2", "hf_nu")]
    trans_good = [c for c in df.columns if c[0] == "Transition" and c[1] in ("rmssd", "sd1", "hf_nu")]
    standing_good = [c for c in df.columns if c[0] == "Standing" and c[1] in ("rmssd", "sd1", "sd2", "hf_nu")]
    resp_good = [c for c in df.columns if c[0] == "Autonomic response" and c[1] in ("delta_rmssd", "hf_hr_pct_change", "lf_hr_pct_change")]
    styler = gradient_good(styler, supine_good)
    styler = gradient_good(styler, trans_good)
    styler = gradient_good(styler, standing_good)
    styler = gradient_good(styler, resp_good)
    styler = gradient_bad(styler, [c for c in df.columns if c == ("Autonomic response", "hr_response")], vmin=0, vmax=30)
    styler = gradient_bad(styler, [c for c in df.columns if c == ("Transition", "peak_hr")], vmin=60, vmax=120)
    styler = highlight_category(styler, ("Autonomic response", "interpretation"), _ORTHO_CAT_COLORS)

    return caption(styler, caption_text)


_HISTORY_DEFAULT_COLS: list[str] = [
    "supine_rmssd",
    "standing_rmssd",
    "delta_rmssd",
    "supine_hr",
    "standing_hr",
    "hr_response",
    "lf_hf_change",
    "hf_response_pct",
    "hf_hr_pct_change",
    "lf_hr_pct_change",
    "interpretation",
]


def table_orthostatic_history(
    results: list,
    dates: list[str] | None = None,
    cols: list[str] | None = None,
    caption_text: str = "Orthostatic history — autonomic response per session",
) -> pd.Styler:
    """Build a condensed multi-session orthostatic history table.

    Shows key autonomic response indicators per session.

    Args:
        results: List of orthostatic result objects in chronological order.
            Accepts both :class:`~cardiolab.protocols.orthostatic.OrthostaticResult`
            (live protocol output) and
            :class:`~cardiolab.database.repository.OrthostaticRecord`
            (database read-back).
        dates: Session labels. Falls back to ``r.date`` or ``"Session N"``.
        cols: Subset of columns to display. Defaults to the standard
            selection. Unknown names raise :class:`ValueError`.
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``results`` is not a list.
        ValueError: If ``results`` is empty, ``dates`` length mismatches, or
            ``cols`` contains unknown column names.

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
                "delta_rmssd": r.delta_rmssd,
                "supine_hr": p.supine.features.mean_hr,
                "standing_hr": p.standing.features.mean_hr,
                "hr_response": r.hr_response,
                "lf_hf_change": r.lf_hf_ratio_change,
                "hf_response_pct": r.hf_response_pct,
                "hf_hr_pct_change": r.hf_hr_pct_change,
                "lf_hr_pct_change": r.lf_hr_pct_change,
                "interpretation": r.interpretation,
            }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Column filtering
    if cols is not None:
        unknown = set(cols) - (set(df.columns) - {"date"})
        if unknown:
            raise ValueError(f"Unknown column(s): {sorted(unknown)}")
        df = df[["date"] + [c for c in cols if c in df.columns]]
    else:
        keep = ["date"] + [c for c in _HISTORY_DEFAULT_COLS if c in df.columns]
        df = df[keep]

    fmt = {c: fmt_float(2) for c in df.select_dtypes("float").columns}

    styler = df.style.format(fmt, na_rep="n/a")
    styler = gradient_good(styler, ["supine_rmssd", "standing_rmssd"])
    styler = gradient_good(styler, ["delta_rmssd", "hf_hr_pct_change", "lf_hr_pct_change"])
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
