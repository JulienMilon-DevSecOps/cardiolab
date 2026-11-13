"""Tabular reporting for the exercise tests of v0.6.0.

Public functions:

* :func:`table_dfa_thresholds_history` — thresholds test after test (or
  entered by hand): heart rate, intensity, status, fit.
* :func:`table_lsct_history` — LSCT test after test: power and heart rate per
  stage, RPE, HRR60, stage 3 target, change against the previous tests.
"""

from __future__ import annotations

import pandas as pd

from cardiolab.labels import lbl
from cardiolab.protocols.dfa_thresholds import ThresholdRecord
from cardiolab.protocols.lsct import LSCTResult, compare_lsct
from cardiolab.reporting._core import (
    apply_labels,
    caption,
    fmt_float,
    gradient_good,
    highlight_category,
    validate_list,
)

_STATUS_COLORS: dict[str, str] = {
    "detected": "#d5f5e3",
    "not_reached": "#fdebd0",
    "unreliable": "#fadbd8",
}
_LSCT_COLORS: dict[str, str] = {
    "improving": "#d5f5e3",
    "stable": "#eaf2f8",
    "fatigue_possible": "#fdebd0",
    "overreaching_possible": "#fadbd8",
}


def table_dfa_thresholds_history(
    records: list[ThresholdRecord],
    labels: dict[str, str] | None = None,
    caption_text: str = "DFA α1 thresholds — HRVT1 (α1 = 0.75) · HRVT2 (α1 = 0.5)",
) -> pd.Styler:
    """Build the history of the thresholds, one row per test or entry.

    Args:
        records: ``ThresholdRecord`` list (e.g. ``repo.load_dfa_thresholds``)
            in chronological order.
        labels: Translation dict, or ``None``.
        caption_text: Caption shown below the table.

    Returns:
        A pandas ``Styler``: status cells coloured, R² graded.

    Raises:
        TypeError: If ``records`` is not a list of ``ThresholdRecord``.
        ValueError: If ``records`` is empty.

    """
    validate_list(records, ThresholdRecord, "records")
    rows = [
        {
            "date": r.date,
            "sport": lbl(labels, f"sport_{r.sport}", r.sport),
            "source": r.source,
            "vt1_hr": r.vt1_hr,
            "vt1_intensity": r.vt1_intensity,
            "vt1_status": r.vt1_status,
            "vt2_hr": r.vt2_hr,
            "vt2_intensity": r.vt2_intensity,
            "vt2_status": r.vt2_status,
            "intensity_unit": r.intensity_unit or "",
            "hr_max_observed": r.hr_max_observed,
            "vt1_r_squared": r.vt1_r_squared,
        }
        for r in records
    ]
    df = pd.DataFrame(rows)
    f0, f2 = fmt_float(0), fmt_float(2)
    styler = df.style.format(
        {
            "vt1_hr": f0,
            "vt2_hr": f0,
            "vt1_intensity": f0,
            "vt2_intensity": f0,
            "hr_max_observed": f0,
            "vt1_r_squared": f2,
            "vt1_status": _translate(labels, "threshold_status_"),
            "vt2_status": _translate(labels, "threshold_status_"),
        },
        na_rep="—",
    )
    for col in ("vt1_status", "vt2_status"):
        styler = highlight_category(styler, col, _STATUS_COLORS)
    styler = gradient_good(styler, ["vt1_r_squared"], vmin=0, vmax=1)
    styler = apply_labels(styler, labels)
    return caption(styler, caption_text)


def table_lsct_history(
    results: list[LSCTResult],
    labels: dict[str, str] | None = None,
    reference_tests: int = 3,
    caption_text: str = "LSCT — power at fixed heart rate, RPE, HRR60",
) -> pd.Styler:
    """Build the LSCT history, with each test compared to the previous ones.

    Args:
        results: Tests in chronological order.
        labels: Translation dict, or ``None``.
        reference_tests: Number of previous tests averaged as reference by
            :func:`~cardiolab.protocols.lsct.compare_lsct`. Defaults to 3.
        caption_text: Caption shown below the table.

    Returns:
        A pandas ``Styler``: stage power graded, interpretation coloured
        (empty for the first test).

    Raises:
        TypeError: If ``results`` is not a list of ``LSCTResult``.
        ValueError: If ``results`` is empty.

    """
    validate_list(results, LSCTResult, "results")
    rows = []
    for i, r in enumerate(results):
        previous = results[max(0, i - reference_tests) : i]
        cmp = compare_lsct(r, previous) if previous else None
        rows.append(
            {
                "date": r.date or f"Test {i + 1}",
                "stage1_power": r.stage(1).mean_power,
                "stage2_power": r.stage(2).mean_power,
                "stage3_power": r.stage(3).mean_power,
                "stage2_rpe": r.stage(2).rpe,
                "stage3_rpe": r.stage(3).rpe,
                "stage3_hr_end": r.stage(3).hr_end,
                "stage3_target_reached": r.stage(3).target_reached,
                "hrr_60": r.hrr_60,
                "power_change_pct": cmp.power_change_pct if cmp else float("nan"),
                "interpretation": cmp.interpretation if cmp else "",
            }
        )
    df = pd.DataFrame(rows)
    f0, f1 = fmt_float(0), fmt_float(1)
    styler = df.style.format(
        {
            "stage1_power": f0,
            "stage2_power": f0,
            "stage3_power": f0,
            "stage3_hr_end": f0,
            "hrr_60": f0,
            "power_change_pct": f1,
            "interpretation": _translate(labels, "lsct_"),
        },
        na_rep="—",
    )
    styler = gradient_good(styler, ["stage2_power", "stage3_power"])
    styler = highlight_category(styler, "interpretation", _LSCT_COLORS)
    styler = apply_labels(styler, labels)
    return caption(styler, caption_text)


def _translate(labels: dict[str, str] | None, prefix: str):
    """Display formatter: a category code shown with its label (``prefix + code``)."""
    return lambda code: lbl(labels, prefix + code, code) if code else ""
