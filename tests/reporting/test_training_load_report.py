"""Tests for cardiolab.reporting.training_load_report."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest
from pandas.io.formats.style import Styler

from cardiolab.analytics.training_load import (
    TrainingLoad,
    compute_atl,
    compute_ctl,
    compute_tsb,
)
from cardiolab.reporting.training_load_report import (
    _ctl_trend,
    _tsb_zone_label,
    summary_training_load,
    table_training_load_history,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tl(
    n: int = 30,
    trimp_val: float = 40.0,
    dates_start: str = "2024-01-01",
) -> TrainingLoad:
    """Build a TrainingLoad with ``n`` days of constant TRIMP."""
    start = date.fromisoformat(dates_start)
    dates = [str(start + timedelta(days=i)) for i in range(n)]
    trimp = np.full(n, trimp_val, dtype=float)
    atl = compute_atl(trimp)
    ctl = compute_ctl(trimp)
    tsb = compute_tsb(ctl, atl)
    return TrainingLoad(dates=dates, trimp=trimp, atl=atl, ctl=ctl, tsb=tsb)


def _make_tl_tsb(tsb_last: float) -> TrainingLoad:
    """Build a TrainingLoad whose last TSB equals *tsb_last* (forced patch)."""
    tl = _make_tl()
    tl.tsb = np.append(tl.tsb[:-1], tsb_last)
    return tl


# ── _tsb_zone_label ───────────────────────────────────────────────────────────


class TestTsbZoneLabel:
    """Tests for _tsb_zone_label."""

    def test_fresh_detraining(self) -> None:
        """TSB > 25 maps to fresh_detraining."""
        assert _tsb_zone_label(30.0) == "fresh_detraining"

    def test_fresh_boundary(self) -> None:
        """TSB just above 25 is still fresh_detraining."""
        assert _tsb_zone_label(25.1) == "fresh_detraining"

    def test_optimal(self) -> None:
        """TSB in 5–25 maps to optimal."""
        assert _tsb_zone_label(15.0) == "optimal"

    def test_optimal_boundary(self) -> None:
        """TSB just above 5 is optimal."""
        assert _tsb_zone_label(5.1) == "optimal"

    def test_neutral(self) -> None:
        """TSB = 0 is neutral."""
        assert _tsb_zone_label(0.0) == "neutral"

    def test_neutral_boundary(self) -> None:
        """TSB just above −10 is neutral."""
        assert _tsb_zone_label(-9.9) == "neutral"

    def test_accumulated_fatigue(self) -> None:
        """TSB in −30 to −10 maps to accumulated_fatigue."""
        assert _tsb_zone_label(-20.0) == "accumulated_fatigue"

    def test_accumulated_boundary(self) -> None:
        """TSB just above −30 is accumulated_fatigue."""
        assert _tsb_zone_label(-29.9) == "accumulated_fatigue"

    def test_overload(self) -> None:
        """TSB < −30 maps to overload."""
        assert _tsb_zone_label(-40.0) == "overload"

    def test_overload_boundary(self) -> None:
        """TSB just below −30 is overload."""
        assert _tsb_zone_label(-30.1) == "overload"

    def test_zero_is_neutral(self) -> None:
        """TSB = 0 lands in the neutral band."""
        assert _tsb_zone_label(0.0) == "neutral"

    def test_exactly_minus_10_is_accumulated(self) -> None:
        """TSB = −10 is not > −10, so it falls into accumulated_fatigue."""
        assert _tsb_zone_label(-10.0) == "accumulated_fatigue"


# ── _ctl_trend ────────────────────────────────────────────────────────────────


class TestCtlTrend:
    """Tests for _ctl_trend."""

    def test_insufficient_data_stable(self) -> None:
        """Return 'stable' when fewer than window+1 values are available."""
        ctl = np.array([10.0, 11.0, 12.0])
        assert _ctl_trend(ctl, window=7) == "stable"

    def test_exactly_window_plus_1(self) -> None:
        """8 values with window=7 and all zeros returns 'stable'."""
        ctl = np.zeros(8)
        assert _ctl_trend(ctl, window=7) == "stable"

    def test_increasing(self) -> None:
        """Steadily rising CTL is classified as 'increasing'."""
        ctl = np.linspace(10.0, 20.0, 30)
        assert _ctl_trend(ctl, window=7) == "increasing"

    def test_decreasing(self) -> None:
        """Steadily falling CTL is classified as 'decreasing'."""
        ctl = np.linspace(20.0, 5.0, 30)
        assert _ctl_trend(ctl, window=7) == "decreasing"

    def test_stable(self) -> None:
        """Constant CTL is classified as 'stable'."""
        ctl = np.full(30, 15.0)
        assert _ctl_trend(ctl, window=7) == "stable"

    def test_custom_threshold(self) -> None:
        """Threshold parameter controls the boundary between stable and trending."""
        ctl = np.zeros(30)
        ctl[-1] = 0.5
        assert _ctl_trend(ctl, window=7, threshold=1.0) == "stable"
        assert _ctl_trend(ctl, window=7, threshold=0.1) == "increasing"


# ── table_training_load_history ───────────────────────────────────────────────


class TestTableTrainingLoadHistory:
    """Tests for table_training_load_history."""

    def test_returns_styler(self) -> None:
        """Return a pandas Styler."""
        assert isinstance(table_training_load_history(_make_tl()), Styler)

    def test_row_count(self) -> None:
        """One row per day of data."""
        styler = table_training_load_history(_make_tl(n=14))
        assert len(styler.data) == 14

    def test_columns_present(self) -> None:
        """All expected columns are present."""
        cols = set(table_training_load_history(_make_tl()).data.columns)
        for col in ("date", "trimp", "atl", "ctl", "tsb", "tsb_zone"):
            assert col in cols, f"Missing column: {col}"

    def test_date_column_matches(self) -> None:
        """Date column contains the original date strings in order."""
        tl = _make_tl(n=3)
        styler = table_training_load_history(tl)
        assert list(styler.data["date"]) == tl.dates

    def test_trimp_values(self) -> None:
        """TRIMP values match those in the TrainingLoad."""
        tl = _make_tl(n=5, trimp_val=55.0)
        styler = table_training_load_history(tl)
        for val in styler.data["trimp"]:
            assert pytest.approx(val, rel=1e-3) == 55.0

    def test_atl_values(self) -> None:
        """ATL values match those in the TrainingLoad."""
        tl = _make_tl(n=10)
        styler = table_training_load_history(tl)
        for i, val in enumerate(styler.data["atl"]):
            assert pytest.approx(val, rel=1e-3) == float(tl.atl[i])

    def test_ctl_values(self) -> None:
        """CTL values match those in the TrainingLoad."""
        tl = _make_tl(n=10)
        styler = table_training_load_history(tl)
        for i, val in enumerate(styler.data["ctl"]):
            assert pytest.approx(val, rel=1e-3) == float(tl.ctl[i])

    def test_tsb_values(self) -> None:
        """TSB values match those in the TrainingLoad."""
        tl = _make_tl(n=10)
        styler = table_training_load_history(tl)
        for i, val in enumerate(styler.data["tsb"]):
            assert pytest.approx(val, rel=1e-3) == float(tl.tsb[i])

    def test_tsb_zone_column_populated(self) -> None:
        """tsb_zone contains no nulls."""
        styler = table_training_load_history(_make_tl())
        assert styler.data["tsb_zone"].notna().all()

    def test_default_caption(self) -> None:
        """Default caption mentions ATL and CTL."""
        styler = table_training_load_history(_make_tl())
        assert "ATL" in styler.caption and "CTL" in styler.caption

    def test_custom_caption(self) -> None:
        """Custom caption is applied verbatim."""
        styler = table_training_load_history(_make_tl(), caption_text="Mon rapport")
        assert styler.caption == "Mon rapport"

    def test_empty_raises(self) -> None:
        """Raise ValueError for an empty TrainingLoad."""
        with pytest.raises(ValueError, match="at least one day"):
            table_training_load_history(TrainingLoad())

    def test_single_day(self) -> None:
        """Single-day TrainingLoad produces a one-row table."""
        styler = table_training_load_history(_make_tl(n=1))
        assert len(styler.data) == 1

    def test_tsb_zone_optimal_label(self) -> None:
        """TSB = 10 yields the 'optimal' zone label."""
        styler = table_training_load_history(_make_tl_tsb(10.0))
        assert styler.data["tsb_zone"].iloc[-1] == "optimal"

    def test_tsb_zone_overload_label(self) -> None:
        """TSB = −35 yields the 'overload' zone label."""
        styler = table_training_load_history(_make_tl_tsb(-35.0))
        assert styler.data["tsb_zone"].iloc[-1] == "overload"


# ── summary_training_load ─────────────────────────────────────────────────────


class TestSummaryTrainingLoad:
    """Tests for summary_training_load."""

    def test_returns_dict(self) -> None:
        """Return a dict."""
        assert isinstance(summary_training_load(_make_tl()), dict)

    def test_keys(self) -> None:
        """Dict contains exactly the five expected keys."""
        result = summary_training_load(_make_tl())
        assert set(result.keys()) == {"atl", "ctl", "tsb", "tsb_zone", "ctl_trend"}

    def test_atl_matches_last(self) -> None:
        """ATL equals the last element of the ATL array."""
        tl = _make_tl()
        result = summary_training_load(tl)
        assert pytest.approx(result["atl"], rel=1e-3) == float(tl.atl[-1])

    def test_ctl_matches_last(self) -> None:
        """CTL equals the last element of the CTL array."""
        tl = _make_tl()
        result = summary_training_load(tl)
        assert pytest.approx(result["ctl"], rel=1e-3) == float(tl.ctl[-1])

    def test_tsb_matches_last(self) -> None:
        """TSB equals the last element of the TSB array."""
        tl = _make_tl()
        result = summary_training_load(tl)
        assert pytest.approx(result["tsb"], rel=1e-3) == float(tl.tsb[-1])

    def test_tsb_zone_is_string(self) -> None:
        """tsb_zone is a string."""
        result = summary_training_load(_make_tl())
        assert isinstance(result["tsb_zone"], str)

    def test_tsb_zone_known_value(self) -> None:
        """TSB = 8 maps to 'optimal'."""
        result = summary_training_load(_make_tl_tsb(8.0))
        assert result["tsb_zone"] == "optimal"

    def test_ctl_trend_is_string(self) -> None:
        """ctl_trend is one of the three expected strings."""
        result = summary_training_load(_make_tl())
        assert result["ctl_trend"] in {"increasing", "stable", "decreasing"}

    def test_ctl_trend_stable_constant(self) -> None:
        """Zero TRIMP → zero CTL everywhere → stable trend."""
        result = summary_training_load(_make_tl(n=30, trimp_val=0.0))
        assert result["ctl_trend"] == "stable"

    def test_ctl_trend_short_series(self) -> None:
        """Too few days to evaluate trend → stable."""
        result = summary_training_load(_make_tl(n=3))
        assert result["ctl_trend"] == "stable"

    def test_empty_raises(self) -> None:
        """Raise ValueError for an empty TrainingLoad."""
        with pytest.raises(ValueError, match="at least one day"):
            summary_training_load(TrainingLoad())

    def test_values_rounded(self) -> None:
        """Numeric values are rounded to 2 decimal places."""
        result = summary_training_load(_make_tl())
        for key in ("atl", "ctl", "tsb"):
            assert isinstance(result[key], float)
            assert round(result[key], 2) == result[key]
