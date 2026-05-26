"""Tests for cardiolab.reporting.hrr."""

from __future__ import annotations

import pytest
from pandas.io.formats.style import Styler

from cardiolab.protocols.hrr import HRRResult
from cardiolab.reporting.hrr import (
    _validate_list,
    table_hrr_history,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_result(**kwargs) -> HRRResult:
    """Build an HRRResult with sensible defaults."""
    defaults = dict(
        date=None,
        hr_peak=175.0,
        hr_at_60s=150.0,
        hrr_60=25.0,
        hrr_60_category="good",
        hr_at_120s=135.0,
        hrr_120=40.0,
        hrr_120_category="excellent",
        duration=120.0,
    )
    defaults.update(kwargs)
    return HRRResult(**defaults)


@pytest.fixture
def one_result() -> HRRResult:
    """Single HRRResult session."""
    return _make_result()


@pytest.fixture
def two_results() -> list[HRRResult]:
    """Two HRRResult sessions."""
    return [
        _make_result(hrr_60=25.0, hrr_60_category="good"),
        _make_result(hrr_60=10.0, hrr_60_category="impaired"),
    ]


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", HRRResult, "results")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], HRRResult, "results")


def test_validate_list_wrong_type(one_result: HRRResult) -> None:
    """Raise TypeError when element has wrong type."""
    with pytest.raises(TypeError, match="results\\[1\\]"):
        _validate_list([one_result, "bad"], HRRResult, "results")


def test_validate_list_ok(one_result: HRRResult) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_result], HRRResult, "results")


# ── table_hrr_history ─────────────────────────────────────────────────────────


class TestTableHrrHistory:
    """Tests for table_hrr_history."""

    def test_returns_styler(self, two_results: list[HRRResult]) -> None:
        """Return a pandas Styler."""
        styler = table_hrr_history(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: HRRResult) -> None:
        """One-row table for a single session."""
        styler = table_hrr_history([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[HRRResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_hrr_history(two_results)
        assert len(styler.data) == 2

    def test_key_columns_present(self, one_result: HRRResult) -> None:
        """All HRR columns are present."""
        styler = table_hrr_history([one_result])
        cols = set(styler.data.columns)
        for col in ("hr_peak", "hr_at_60s", "hrr_60", "hrr_60_category",
                    "hrr_120", "hrr_120_category", "duration"):
            assert col in cols

    def test_custom_dates(self, two_results: list[HRRResult]) -> None:
        """Custom date labels appear in the date column."""
        dates = ["2024-01-01", "2024-01-08"]
        styler = table_hrr_history(two_results, dates=dates)
        assert list(styler.data["date"]) == dates

    def test_default_dates_fallback(self, two_results: list[HRRResult]) -> None:
        """Default date labels follow 'Session N' pattern."""
        styler = table_hrr_history(two_results)
        assert styler.data["date"].iloc[0] == "Session 1"
        assert styler.data["date"].iloc[1] == "Session 2"

    def test_result_date_takes_priority(self) -> None:
        """Result.date takes priority over generated labels."""
        r = _make_result(date="2024-06-01")
        styler = table_hrr_history([r])
        assert styler.data["date"].iloc[0] == "2024-06-01"

    def test_dates_length_mismatch_raises(self, two_results: list[HRRResult]) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_hrr_history(two_results, dates=["only one"])

    def test_caption(self, one_result: HRRResult) -> None:
        """Custom caption is applied."""
        styler = table_hrr_history([one_result], caption_text="HRR Test")
        assert styler.caption == "HRR Test"

    def test_hrr_60_value(self, one_result: HRRResult) -> None:
        """HRR1 value is stored correctly."""
        styler = table_hrr_history([one_result])
        assert pytest.approx(styler.data["hrr_60"].iloc[0], rel=1e-3) == 25.0

    def test_hrr_60_category_value(self, one_result: HRRResult) -> None:
        """HRR1 category is stored correctly."""
        styler = table_hrr_history([one_result])
        assert styler.data["hrr_60_category"].iloc[0] == "good"

    def test_nan_hrr_120_handled(self) -> None:
        """NaN hrr_120 does not crash."""
        r = _make_result(hr_at_120s=float("nan"), hrr_120=float("nan"), hrr_120_category="")
        styler = table_hrr_history([r])
        assert styler is not None

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_hrr_history("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_hrr_history([])

    def test_hr_peak_value(self, one_result: HRRResult) -> None:
        """Peak HR value is stored correctly."""
        styler = table_hrr_history([one_result])
        assert pytest.approx(styler.data["hr_peak"].iloc[0], rel=1e-3) == 175.0

    def test_categories_in_multi_session(self, two_results: list[HRRResult]) -> None:
        """Both categories appear in the category column."""
        styler = table_hrr_history(two_results)
        cats = list(styler.data["hrr_60_category"])
        assert "good" in cats
        assert "impaired" in cats
