"""Tabular reporting for the resting HRV protocol.

Two public functions:

* :func:`table_resting_history` — one row per session, key metrics with
  colour gradients.
* :func:`table_resting_session` — single-session detail with all metrics
  arranged in rows.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.protocols.resting import HRVFeatures
from cardiolab.reporting._core import (
    apply_labels,
    caption,
    fmt_float,
    fmt_nan,
    gradient_bad,
    gradient_good,
)

# ── Default column selection ──────────────────────────────────────────────────

_HISTORY_COLS: list[str] = [
    "date",
    "rmssd",
    "sdnn",
    "mean_hr",
    "sd1",
    "sd2",
    "sd_ratio",
    "dfa_alpha1",
    "apen",
    "sampen",
    "score",
]


# ── Public functions ──────────────────────────────────────────────────────────


def table_resting_history(
    features_list: list[HRVFeatures],
    cols: list[str] | None = None,
    labels: dict[str, str] | None = None,
    caption_text: str = "Resting HRV history — red = low · green = high",
) -> pd.Styler:
    """Build a multi-session history table for resting HRV.

    Each row represents one session.  Key metrics are highlighted with
    directional colour gradients (green = better).

    Args:
        features_list: List of :class:`~cardiolab.protocols.resting.HRVFeatures`
            in chronological order.
        cols: Column names to include. Defaults to the standard selection
            (date, RMSSD, SDNN, mean HR, SD1/SD2, DFA α1, ApEn, SampEn, score).
        caption_text: Caption shown below the table.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``features_list`` is not a list or contains non-HRVFeatures.
        ValueError: If ``features_list`` is empty.

    """
    _validate_list(features_list, HRVFeatures, "features_list")

    cols = cols or _HISTORY_COLS
    rows = [f.to_dict() if hasattr(f, "to_dict") else vars(f) for f in features_list]
    df = pd.DataFrame(rows)

    if cols is not _HISTORY_COLS:
        unknown = set(cols) - set(df.columns)
        if unknown:
            raise ValueError(f"Unknown column(s): {sorted(unknown)}")
    cols = [c for c in cols if c in df.columns]
    df = df[cols]

    nan_cols = [c for c in cols if "dfa" in c or "apen" in c or "sampen" in c]
    float_cols = [c for c in df.select_dtypes("float").columns if c not in nan_cols]

    fmt: dict = {c: fmt_float(1) for c in float_cols}
    fmt.update({c: fmt_nan(3) for c in nan_cols if c in cols})
    if "score" in cols:
        fmt["score"] = fmt_float(1)
    if "sd_ratio" in cols:
        fmt["sd_ratio"] = fmt_float(3)

    styler = df.style.format(fmt)
    styler = gradient_good(styler, ["rmssd", "sd1", "sd2", "hf_nu"], vmin=0)
    styler = gradient_good(styler, ["score"], vmin=0, vmax=100)
    styler = gradient_good(styler, ["dfa_alpha1"], vmin=0.5, vmax=1.25)
    styler = gradient_good(styler, ["apen"], vmin=0.5, vmax=1.8)
    styler = gradient_good(styler, ["sampen"], vmin=0.5, vmax=2.0)
    styler = gradient_bad(styler, ["mean_hr"])
    styler = apply_labels(styler, labels)
    return caption(styler, caption_text)


def table_resting_session(
    features: HRVFeatures,
    caption_text: str | None = None,
) -> pd.Styler:
    """Build a single-session detail table for resting HRV.

    Metrics are grouped into domains (temporal, frequency, non-linear, score)
    and displayed as row → value pairs.

    Args:
        features: :class:`~cardiolab.protocols.resting.HRVFeatures` for one
            session.
        caption_text: Caption shown below the table. Defaults to the session
            date when available.

    Returns:
        A :class:`~pandas.io.formats.style.Styler` ready for ``display()``.

    Raises:
        TypeError: If ``features`` is not an HRVFeatures.

    """
    if not isinstance(features, HRVFeatures):
        raise TypeError(
            f"features must be an HRVFeatures, got {type(features).__name__}"
        )

    _nan = fmt_nan(3)

    rows = [
        # Temporal
        ("RMSSD (ms)", f"{features.rmssd:.2f}", "Temporal"),
        ("ln(RMSSD)", f"{features.ln_rmssd:.3f}", "Temporal"),
        ("SDNN (ms)", f"{features.sdnn:.2f}", "Temporal"),
        ("pNN50 (%)", f"{features.pnn50:.1f}", "Temporal"),
        ("Mean HR (bpm)", f"{features.mean_hr:.1f}", "Temporal"),
        # Frequency
        ("Method", features.method or "—", "Frequency"),
        ("VLF (ms²)", f"{features.vlf:.2f}", "Frequency"),
        ("LF (ms²)", f"{features.lf:.2f}", "Frequency"),
        ("HF (ms²)", f"{features.hf:.2f}", "Frequency"),
        ("LF/HF", f"{features.lf_hf:.3f}", "Frequency"),
        ("HF% (%)", f"{features.hf_pct:.1f}", "Frequency"),
        ("LF_nu", f"{features.lf_nu:.3f}", "Frequency"),
        ("HF_nu", f"{features.hf_nu:.3f}", "Frequency"),
        # Non-linear
        ("SD1 (ms)", f"{features.sd1:.2f}", "Non-linear"),
        ("SD2 (ms)", f"{features.sd2:.2f}", "Non-linear"),
        ("SD1/SD2", f"{features.sd_ratio:.3f}", "Non-linear"),
        ("DFA α1", _nan(features.dfa_alpha1), "Non-linear"),
        ("ApEn", _nan(features.apen), "Non-linear"),
        ("SampEn", _nan(features.sampen), "Non-linear"),
        # Score
        ("HRV Score", f"{features.score:.1f} / 100", "Score"),
    ]

    df = pd.DataFrame(rows, columns=["Metric", "Value", "Domain"])
    df = df.set_index("Metric")

    cap = caption_text or (
        f"Session {features.date}" if features.date else "Session detail"
    )
    return df.style.set_caption(cap)


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
