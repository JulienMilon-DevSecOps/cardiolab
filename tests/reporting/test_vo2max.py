"""Tests for cardiolab.reporting.vo2max."""

from __future__ import annotations

import math

import pytest
from pandas.io.formats.style import Styler

from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.reporting.vo2max import (
    _validate_list,
    table_vo2max_history,
    table_vo2max_session,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_result(**kwargs) -> VO2maxResult:
    """Build a VO2maxResult with sensible defaults."""
    defaults = dict(
        date=None,
        vo2max_uth=float("nan"),
        vo2max_esco_flatt=42.5,
        vo2max_ln_rmssd=44.1,
        hr_rest=58.0,
        hr_max=float("nan"),
        rmssd_used=45.0,
        ln_rmssd_used=3.81,
        fitness_category="good",
    )
    defaults.update(kwargs)
    return VO2maxResult(**defaults)


def _make_result_with_uth(**kwargs) -> VO2maxResult:
    """Build a VO2maxResult that includes a valid Uth estimate."""
    return _make_result(
        vo2max_uth=55.0,
        hr_max=185.0,
        fitness_category="very_good",
        **kwargs,
    )


@pytest.fixture
def one_result() -> VO2maxResult:
    """Single VO2maxResult without Uth estimate."""
    return _make_result()


@pytest.fixture
def one_result_uth() -> VO2maxResult:
    """Single VO2maxResult with valid Uth estimate."""
    return _make_result_with_uth()


@pytest.fixture
def two_results() -> list[VO2maxResult]:
    """Two VO2maxResult sessions."""
    return [
        _make_result(vo2max_esco_flatt=38.0, fitness_category="fair"),
        _make_result(vo2max_esco_flatt=50.0, fitness_category="very_good"),
    ]


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", VO2maxResult, "results")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], VO2maxResult, "results")


def test_validate_list_wrong_type(one_result: VO2maxResult) -> None:
    """Raise TypeError when element has wrong type."""
    with pytest.raises(TypeError, match="results\\[1\\]"):
        _validate_list([one_result, "bad"], VO2maxResult, "results")


def test_validate_list_ok(one_result: VO2maxResult) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_result], VO2maxResult, "results")


# ── table_vo2max_history ──────────────────────────────────────────────────────


class TestTableVo2maxHistory:
    """Tests for table_vo2max_history."""

    def test_returns_styler(self, two_results: list[VO2maxResult]) -> None:
        """Return a pandas Styler."""
        styler = table_vo2max_history(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: VO2maxResult) -> None:
        """One-row table for a single session."""
        styler = table_vo2max_history([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[VO2maxResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_vo2max_history(two_results)
        assert len(styler.data) == 2

    def test_key_columns_present(self, one_result: VO2maxResult) -> None:
        """All VO2max columns are present."""
        styler = table_vo2max_history([one_result])
        cols = set(styler.data.columns)
        for col in (
            "vo2max_esco_flatt",
            "vo2max_ln_rmssd",
            "hr_rest",
            "rmssd_used",
            "fitness_category",
        ):
            assert col in cols

    def test_vo2max_uth_excluded_when_all_nan(self, one_result: VO2maxResult) -> None:
        """vo2max_uth column not included in gradient when all values are NaN."""
        styler = table_vo2max_history([one_result])
        assert math.isnan(styler.data["vo2max_uth"].iloc[0])

    def test_vo2max_uth_included_when_present(
        self, one_result_uth: VO2maxResult
    ) -> None:
        """vo2max_uth value is stored correctly when provided."""
        styler = table_vo2max_history([one_result_uth])
        assert pytest.approx(styler.data["vo2max_uth"].iloc[0], rel=1e-3) == 55.0

    def test_custom_dates(self, two_results: list[VO2maxResult]) -> None:
        """Custom date labels appear in the date column."""
        dates = ["2024-01-01", "2024-01-08"]
        styler = table_vo2max_history(two_results, dates=dates)
        assert list(styler.data["date"]) == dates

    def test_default_dates_fallback(self, two_results: list[VO2maxResult]) -> None:
        """Default date labels follow 'Session N' pattern."""
        styler = table_vo2max_history(two_results)
        assert styler.data["date"].iloc[0] == "Session 1"

    def test_result_date_takes_priority(self) -> None:
        """Result.date takes priority over generated labels."""
        r = _make_result(date="2024-08-01")
        styler = table_vo2max_history([r])
        assert styler.data["date"].iloc[0] == "2024-08-01"

    def test_dates_length_mismatch_raises(
        self, two_results: list[VO2maxResult]
    ) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_vo2max_history(two_results, dates=["only one"])

    def test_caption(self, one_result: VO2maxResult) -> None:
        """Custom caption is applied."""
        styler = table_vo2max_history([one_result], caption_text="VO2 Test")
        assert styler.caption == "VO2 Test"

    def test_esco_flatt_value(self, one_result: VO2maxResult) -> None:
        """Esco-Flatt estimate is stored correctly."""
        styler = table_vo2max_history([one_result])
        assert pytest.approx(styler.data["vo2max_esco_flatt"].iloc[0], rel=1e-3) == 42.5

    def test_fitness_category_value(self, one_result: VO2maxResult) -> None:
        """Fitness category is stored correctly."""
        styler = table_vo2max_history([one_result])
        assert styler.data["fitness_category"].iloc[0] == "good"

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_vo2max_history("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_vo2max_history([])


# ── table_vo2max_session ──────────────────────────────────────────────────────


class TestTableVo2maxSession:
    """Tests for table_vo2max_session."""

    def test_returns_styler(self, one_result: VO2maxResult) -> None:
        """Return a pandas Styler."""
        styler = table_vo2max_session(one_result)
        assert isinstance(styler, Styler)

    def test_columns_valeur_groupe(self, one_result: VO2maxResult) -> None:
        """Table has Valeur and Groupe columns."""
        styler = table_vo2max_session(one_result)
        assert list(styler.data.columns) == ["Valeur", "Groupe"]

    def test_index_contains_models(self, one_result: VO2maxResult) -> None:
        """All three model rows are present in the index."""
        styler = table_vo2max_session(one_result)
        idx = set(styler.data.index)
        assert "VO2max Esco-Flatt (mL/kg/min)" in idx
        assert "VO2max ln-RMSSD (mL/kg/min)" in idx
        assert "VO2max Uth (mL/kg/min)" in idx

    def test_uth_nan_renders_na(self, one_result: VO2maxResult) -> None:
        """NaN Uth value renders as 'n/a'."""
        styler = table_vo2max_session(one_result)
        uth_val = styler.data.loc["VO2max Uth (mL/kg/min)", "Valeur"]
        assert uth_val == "n/a"

    def test_esco_flatt_value_in_table(self, one_result: VO2maxResult) -> None:
        """Esco-Flatt estimate is rendered in the table."""
        styler = table_vo2max_session(one_result)
        val = styler.data.loc["VO2max Esco-Flatt (mL/kg/min)", "Valeur"]
        assert "42" in val

    def test_fitness_category_in_table(self, one_result: VO2maxResult) -> None:
        """Fitness category row is present."""
        styler = table_vo2max_session(one_result)
        assert "Catégorie fitness" in styler.data.index

    def test_default_caption_uses_date(self) -> None:
        """Default caption includes the session date."""
        r = _make_result(date="2024-09-01")
        styler = table_vo2max_session(r)
        assert "2024-09-01" in styler.caption

    def test_custom_caption(self, one_result: VO2maxResult) -> None:
        """Custom caption is applied."""
        styler = table_vo2max_session(one_result, caption_text="Custom")
        assert styler.caption == "Custom"

    def test_no_date_fallback_caption(self, one_result: VO2maxResult) -> None:
        """Caption falls back when date is None."""
        styler = table_vo2max_session(one_result)
        assert "VO2max" in styler.caption

    def test_wrong_type_raises(self) -> None:
        """Raise TypeError when input is not a VO2maxResult."""
        with pytest.raises(TypeError, match="VO2maxResult"):
            table_vo2max_session("bad input")

    def test_group_column_values(self, one_result: VO2maxResult) -> None:
        """Groupe column contains expected group names."""
        styler = table_vo2max_session(one_result)
        groups = set(styler.data["Groupe"])
        assert {"Model", "Inputs", "Result"} <= groups
