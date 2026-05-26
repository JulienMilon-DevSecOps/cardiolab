"""Tests for cardiolab.reporting.coherence."""

from __future__ import annotations

import pytest
from pandas.io.formats.style import Styler

from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.reporting.coherence import (
    _coherence_category,
    _validate_list,
    table_coherence_history,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_result(**kwargs) -> CoherenceResult:
    """Build a CoherenceResult with sensible defaults."""
    defaults = dict(
        date=None,
        coherence_score=65.0,
        resonance_freq=0.100,
        peak_power=1200.0,
        total_power_resonance=1600.0,
        rmssd=45.0,
        sdnn=52.0,
        mean_hr=62.0,
        duration=300.0,
    )
    defaults.update(kwargs)
    return CoherenceResult(**defaults)


@pytest.fixture
def one_result() -> CoherenceResult:
    """Single CoherenceResult session with high coherence."""
    return _make_result()


@pytest.fixture
def two_results() -> list[CoherenceResult]:
    """Two CoherenceResult sessions: high and low coherence."""
    return [
        _make_result(coherence_score=70.0),
        _make_result(coherence_score=30.0),
    ]


# ── _coherence_category ───────────────────────────────────────────────────────


def test_coherence_category_high() -> None:
    """Score ≥ 60 → 'high'."""
    assert _coherence_category(60.0) == "high"
    assert _coherence_category(80.0) == "high"


def test_coherence_category_moderate() -> None:
    """Score in [40, 60) → 'moderate'."""
    assert _coherence_category(40.0) == "moderate"
    assert _coherence_category(55.0) == "moderate"


def test_coherence_category_low() -> None:
    """Score < 40 → 'low'."""
    assert _coherence_category(39.9) == "low"
    assert _coherence_category(0.0) == "low"


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", CoherenceResult, "results")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], CoherenceResult, "results")


def test_validate_list_wrong_type(one_result: CoherenceResult) -> None:
    """Raise TypeError when element has wrong type."""
    with pytest.raises(TypeError, match="results\\[1\\]"):
        _validate_list([one_result, "bad"], CoherenceResult, "results")


def test_validate_list_ok(one_result: CoherenceResult) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_result], CoherenceResult, "results")


# ── table_coherence_history ───────────────────────────────────────────────────


class TestTableCoherenceHistory:
    """Tests for table_coherence_history."""

    def test_returns_styler(self, two_results: list[CoherenceResult]) -> None:
        """Return a pandas Styler."""
        styler = table_coherence_history(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: CoherenceResult) -> None:
        """One-row table for a single session."""
        styler = table_coherence_history([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[CoherenceResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_coherence_history(two_results)
        assert len(styler.data) == 2

    def test_key_columns_present(self, one_result: CoherenceResult) -> None:
        """All coherence columns are present."""
        styler = table_coherence_history([one_result])
        cols = set(styler.data.columns)
        for col in ("coherence_score", "category", "resonance_freq",
                    "peak_power", "total_power_resonance",
                    "rmssd", "sdnn", "mean_hr", "duration"):
            assert col in cols

    def test_category_derived_correctly(self, one_result: CoherenceResult) -> None:
        """Category column is derived from coherence score."""
        styler = table_coherence_history([one_result])
        assert styler.data["category"].iloc[0] == "high"

    def test_low_score_gets_low_category(self) -> None:
        """Score < 40 produces 'low' category."""
        r = _make_result(coherence_score=25.0)
        styler = table_coherence_history([r])
        assert styler.data["category"].iloc[0] == "low"

    def test_moderate_score_category(self) -> None:
        """Score in [40, 60) produces 'moderate' category."""
        r = _make_result(coherence_score=50.0)
        styler = table_coherence_history([r])
        assert styler.data["category"].iloc[0] == "moderate"

    def test_custom_dates(self, two_results: list[CoherenceResult]) -> None:
        """Custom date labels appear in the date column."""
        dates = ["2024-01-01", "2024-01-08"]
        styler = table_coherence_history(two_results, dates=dates)
        assert list(styler.data["date"]) == dates

    def test_default_dates_fallback(self, two_results: list[CoherenceResult]) -> None:
        """Default date labels follow 'Session N' pattern."""
        styler = table_coherence_history(two_results)
        assert styler.data["date"].iloc[0] == "Session 1"

    def test_result_date_takes_priority(self) -> None:
        """Result.date takes priority over generated labels."""
        r = _make_result(date="2024-07-01")
        styler = table_coherence_history([r])
        assert styler.data["date"].iloc[0] == "2024-07-01"

    def test_dates_length_mismatch_raises(self, two_results: list[CoherenceResult]) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_coherence_history(two_results, dates=["only one"])

    def test_caption(self, one_result: CoherenceResult) -> None:
        """Custom caption is applied."""
        styler = table_coherence_history([one_result], caption_text="Coh Test")
        assert styler.caption == "Coh Test"

    def test_coherence_score_value(self, one_result: CoherenceResult) -> None:
        """Coherence score value is stored correctly."""
        styler = table_coherence_history([one_result])
        assert pytest.approx(styler.data["coherence_score"].iloc[0], rel=1e-3) == 65.0

    def test_resonance_freq_value(self, one_result: CoherenceResult) -> None:
        """Resonance frequency is stored correctly."""
        styler = table_coherence_history([one_result])
        assert pytest.approx(styler.data["resonance_freq"].iloc[0], rel=1e-3) == 0.100

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_coherence_history("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_coherence_history([])
