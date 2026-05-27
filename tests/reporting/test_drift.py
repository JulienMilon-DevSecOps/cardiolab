"""Tests for cardiolab.reporting.drift."""

from __future__ import annotations

import pytest
from pandas.io.formats.style import Styler

from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.reporting.drift import (
    _validate_list,
    table_drift_history,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_result(**kwargs) -> DriftResult:
    """Build a DriftResult with sensible defaults."""
    defaults = dict(
        date=None,
        drift_rate=0.8,
        drift_magnitude=4.0,
        r_squared=0.85,
        drift_detected=True,
        initial_hr=140.0,
        final_hr=144.0,
        n_windows=8,
        interpretation="mild",
        duration=480.0,
    )
    defaults.update(kwargs)
    return DriftResult(**defaults)


@pytest.fixture
def one_result() -> DriftResult:
    """Single DriftResult session."""
    return _make_result()


@pytest.fixture
def two_results() -> list[DriftResult]:
    """Two DriftResult sessions."""
    return [
        _make_result(drift_rate=0.3, interpretation="no_drift"),
        _make_result(drift_rate=2.0, interpretation="moderate"),
    ]


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", DriftResult, "results")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], DriftResult, "results")


def test_validate_list_wrong_type(one_result: DriftResult) -> None:
    """Raise TypeError when element has wrong type."""
    with pytest.raises(TypeError, match="results\\[1\\]"):
        _validate_list([one_result, "bad"], DriftResult, "results")


def test_validate_list_ok(one_result: DriftResult) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_result], DriftResult, "results")


# ── table_drift_history ───────────────────────────────────────────────────────


class TestTableDriftHistory:
    """Tests for table_drift_history."""

    def test_returns_styler(self, two_results: list[DriftResult]) -> None:
        """Return a pandas Styler."""
        styler = table_drift_history(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: DriftResult) -> None:
        """One-row table for a single session."""
        styler = table_drift_history([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[DriftResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_drift_history(two_results)
        assert len(styler.data) == 2

    def test_key_columns_present(self, one_result: DriftResult) -> None:
        """All drift columns are present."""
        styler = table_drift_history([one_result])
        cols = set(styler.data.columns)
        for col in (
            "drift_rate",
            "drift_magnitude",
            "r_squared",
            "initial_hr",
            "final_hr",
            "n_windows",
            "duration",
            "interpretation",
        ):
            assert col in cols

    def test_custom_dates(self, two_results: list[DriftResult]) -> None:
        """Custom date labels appear in the date column."""
        dates = ["2024-01-01", "2024-01-08"]
        styler = table_drift_history(two_results, dates=dates)
        assert list(styler.data["date"]) == dates

    def test_default_dates_fallback(self, two_results: list[DriftResult]) -> None:
        """Default date labels follow 'Session N' pattern."""
        styler = table_drift_history(two_results)
        assert styler.data["date"].iloc[0] == "Session 1"

    def test_result_date_takes_priority(self) -> None:
        """Result.date takes priority over generated labels."""
        r = _make_result(date="2024-06-15")
        styler = table_drift_history([r])
        assert styler.data["date"].iloc[0] == "2024-06-15"

    def test_dates_length_mismatch_raises(self, two_results: list[DriftResult]) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_drift_history(two_results, dates=["only one"])

    def test_caption(self, one_result: DriftResult) -> None:
        """Custom caption is applied."""
        styler = table_drift_history([one_result], caption_text="Drift Test")
        assert styler.caption == "Drift Test"

    def test_drift_rate_value(self, one_result: DriftResult) -> None:
        """Drift rate value is stored correctly."""
        styler = table_drift_history([one_result])
        assert pytest.approx(styler.data["drift_rate"].iloc[0], rel=1e-3) == 0.8

    def test_interpretation_value(self, one_result: DriftResult) -> None:
        """Interpretation is stored correctly."""
        styler = table_drift_history([one_result])
        assert styler.data["interpretation"].iloc[0] == "mild"

    def test_r_squared_value(self, one_result: DriftResult) -> None:
        """R² value is stored correctly."""
        styler = table_drift_history([one_result])
        assert pytest.approx(styler.data["r_squared"].iloc[0], rel=1e-3) == 0.85

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_drift_history("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_drift_history([])

    def test_interpretation_categories(self, two_results: list[DriftResult]) -> None:
        """Both interpretations appear in the interpretation column."""
        styler = table_drift_history(two_results)
        interps = list(styler.data["interpretation"])
        assert "no_drift" in interps
        assert "moderate" in interps
