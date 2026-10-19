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
    form_zone,
)
from cardiolab.reporting.training_load_report import (
    _ctl_trend,
    summary_training_load,
    table_training_load_history,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tl(
    n: int = 60,
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


def _make_tl_form(form_last: float) -> TrainingLoad:
    """Build a TrainingLoad whose last relative form equals *form_last* (forced patch)."""
    tl = _make_tl()
    tl.form = np.append(tl.form[:-1], form_last)
    return tl


# ── form_zone (relative form, 0.5.0) ──────────────────────────────────────────


class TestFormZone:
    """Zones of the relative form (TSB in % of CTL)."""

    @pytest.mark.parametrize(
        ("form", "zone"),
        [
            (30.0, "fresh_detraining"),
            (20.1, "fresh_detraining"),
            (15.0, "optimal"),
            (5.1, "optimal"),
            (0.0, "neutral"),
            (-29.9, "neutral"),
            (-40.0, "accumulated_fatigue"),
            (-49.9, "accumulated_fatigue"),
            (-50.0, "overload"),
            (-163.0, "overload"),
        ],
    )
    def test_bounds(self, form: float, zone: str) -> None:
        """+20 / +5 / −30 / −50 % (ATL / CTL 0.8 / 0.95 / 1.3 / 1.5)."""
        assert form_zone(form) == zone

    def test_nan_is_none(self) -> None:
        """No zone before 42 days of history."""
        assert form_zone(float("nan")) is None


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
        for col in ("date", "trimp", "atl", "ctl", "tsb", "form_pct", "tsb_zone"):
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

    def test_tsb_zone_after_42_days(self) -> None:
        """tsb_zone is empty for the first 42 days, filled after."""
        zones = table_training_load_history(_make_tl()).data["tsb_zone"]
        assert zones.iloc[:42].isna().all()
        assert zones.iloc[42:].notna().all()

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
        """Form +10 % yields the 'optimal' zone label."""
        styler = table_training_load_history(_make_tl_form(10.0))
        assert styler.data["tsb_zone"].iloc[-1] == "optimal"

    def test_tsb_zone_overload_label(self) -> None:
        """Form −60 % yields the 'overload' zone label."""
        styler = table_training_load_history(_make_tl_form(-60.0))
        assert styler.data["tsb_zone"].iloc[-1] == "overload"

    def test_zone_independent_of_load_scale(self) -> None:
        """×10 loads (session RPE vs HRV method): same form, same zones."""
        small = table_training_load_history(_make_tl(trimp_val=40.0)).data
        large = table_training_load_history(_make_tl(trimp_val=400.0)).data
        assert list(small["tsb_zone"]) == list(large["tsb_zone"])
        np.testing.assert_allclose(small["form_pct"], large["form_pct"])


# ── summary_training_load ─────────────────────────────────────────────────────


class TestSummaryTrainingLoad:
    """Tests for summary_training_load."""

    def test_returns_dict(self) -> None:
        """Return a dict."""
        assert isinstance(summary_training_load(_make_tl()), dict)

    def test_keys(self) -> None:
        """Dict contains exactly the expected keys."""
        result = summary_training_load(_make_tl())
        assert set(result.keys()) == {
            "atl",
            "ctl",
            "tsb",
            "form_pct",
            "load_ratio",
            "tsb_zone",
            "ctl_trend",
        }

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
        """Form +8 % maps to 'optimal', ratio 0.92."""
        result = summary_training_load(_make_tl_form(8.0))
        assert result["tsb_zone"] == "optimal"
        assert result["load_ratio"] == pytest.approx(0.92)

    def test_short_history_no_zone(self) -> None:
        """Fewer than 42 days: no form, no zone."""
        result = summary_training_load(_make_tl(n=20))
        assert result["tsb_zone"] is None
        assert result["form_pct"] is None

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
