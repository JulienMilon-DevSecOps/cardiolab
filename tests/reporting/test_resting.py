"""Tests for cardiolab.reporting.resting."""

from __future__ import annotations

import pytest
from pandas.io.formats.style import Styler

from cardiolab.protocols.resting import HRVFeatures
from cardiolab.reporting.resting import (
    _validate_list,
    table_resting_history,
    table_resting_session,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_features(**kwargs) -> HRVFeatures:
    """Build an HRVFeatures instance with sensible defaults."""
    defaults = dict(
        date="2024-01-01",
        rmssd=42.0,
        ln_rmssd=3.74,
        sdnn=55.0,
        pnn50=28.0,
        mean_hr=60.0,
        vlf=200.0,
        lf=500.0,
        hf=800.0,
        lf_hf=0.625,
        hf_pct=0.53,
        lf_nu=0.38,
        hf_nu=0.61,
        sd1=29.7,
        sd2=70.3,
        sd_ratio=0.42,
        dfa_alpha1=1.05,
        apen=1.20,
        sampen=1.35,
        score=72.0,
        method="welch",
    )
    defaults.update(kwargs)
    return HRVFeatures(**defaults)


@pytest.fixture
def one_feature() -> HRVFeatures:
    """Single HRVFeatures session."""
    return _make_features()


@pytest.fixture
def two_features() -> list[HRVFeatures]:
    """Two HRVFeatures sessions."""
    return [
        _make_features(date="2024-01-01", rmssd=42.0, score=70.0),
        _make_features(date="2024-01-08", rmssd=55.0, score=85.0),
    ]


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", HRVFeatures, "features_list")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], HRVFeatures, "features_list")


def test_validate_list_wrong_type() -> None:
    """Raise TypeError when an element has the wrong type."""
    with pytest.raises(TypeError, match="features_list\\[0\\]"):
        _validate_list(["not_an_hrv"], HRVFeatures, "features_list")


def test_validate_list_ok(one_feature: HRVFeatures) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_feature], HRVFeatures, "features_list")


# ── table_resting_history ─────────────────────────────────────────────────────


class TestTableRestingHistory:
    """Tests for table_resting_history."""

    def test_returns_styler(self, two_features: list[HRVFeatures]) -> None:
        """Return a pandas Styler."""
        styler = table_resting_history(two_features)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_feature: HRVFeatures) -> None:
        """One-row table for a single session."""
        styler = table_resting_history([one_feature])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_features: list[HRVFeatures]) -> None:
        """Two-row table for two sessions."""
        styler = table_resting_history(two_features)
        assert len(styler.data) == 2

    def test_default_columns_present(self, two_features: list[HRVFeatures]) -> None:
        """Key columns exist in the default column set."""
        styler = table_resting_history(two_features)
        cols = list(styler.data.columns)
        for expected in ("rmssd", "sdnn", "mean_hr", "score"):
            assert expected in cols

    def test_custom_cols(self, two_features: list[HRVFeatures]) -> None:
        """Restrict output to requested columns."""
        styler = table_resting_history(two_features, cols=["date", "rmssd"])
        assert list(styler.data.columns) == ["date", "rmssd"]

    def test_missing_cols_silently_dropped(
        self, two_features: list[HRVFeatures]
    ) -> None:
        """Unknown column names are ignored."""
        styler = table_resting_history(
            two_features, cols=["date", "rmssd", "nonexistent"]
        )
        assert "nonexistent" not in styler.data.columns
        assert "rmssd" in styler.data.columns

    def test_caption(self, two_features: list[HRVFeatures]) -> None:
        """Custom caption is applied."""
        styler = table_resting_history(two_features, caption_text="My caption")
        assert styler.caption == "My caption"

    def test_default_caption(self, two_features: list[HRVFeatures]) -> None:
        """Default caption contains expected keywords."""
        styler = table_resting_history(two_features)
        text = styler.caption.lower()
        assert "rouge" in text or "historique" in text

    def test_rmssd_values_in_data(self, two_features: list[HRVFeatures]) -> None:
        """RMSSD values are stored correctly per session."""
        styler = table_resting_history(two_features)
        df = styler.data
        assert pytest.approx(df["rmssd"].iloc[0], rel=1e-3) == 42.0
        assert pytest.approx(df["rmssd"].iloc[1], rel=1e-3) == 55.0

    def test_not_a_list_raises_type_error(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_resting_history("not a list")

    def test_empty_list_raises_value_error(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_resting_history([])

    def test_wrong_type_raises_type_error(self, one_feature: HRVFeatures) -> None:
        """Raise TypeError when list contains non-HRVFeatures."""
        with pytest.raises(TypeError):
            table_resting_history([one_feature, "bad"])

    def test_nan_dfa_handled(self) -> None:
        """NaN values in DFA/Apen/SampEn columns do not crash."""
        f = _make_features(
            dfa_alpha1=float("nan"), apen=float("nan"), sampen=float("nan")
        )
        styler = table_resting_history([f])
        assert styler is not None

    def test_score_column_formatted(self, two_features: list[HRVFeatures]) -> None:
        """Score column is present in the output."""
        styler = table_resting_history(two_features)
        assert "score" in styler.data.columns


# ── table_resting_session ─────────────────────────────────────────────────────


class TestTableRestingSession:
    """Tests for table_resting_session."""

    def test_returns_styler(self, one_feature: HRVFeatures) -> None:
        """Return a pandas Styler."""
        styler = table_resting_session(one_feature)
        assert isinstance(styler, Styler)

    def test_index_contains_rmssd(self, one_feature: HRVFeatures) -> None:
        """RMSSD row is present in the index."""
        styler = table_resting_session(one_feature)
        assert "RMSSD (ms)" in styler.data.index

    def test_columns_metric_value_domain(self, one_feature: HRVFeatures) -> None:
        """Table has exactly Value and Domain columns."""
        styler = table_resting_session(one_feature)
        assert list(styler.data.columns) == ["Value", "Domain"]

    def test_domain_groups_present(self, one_feature: HRVFeatures) -> None:
        """All four domain groups appear in the Domain column."""
        styler = table_resting_session(one_feature)
        domains = set(styler.data["Domain"])
        assert {"Temporal", "Frequency", "Non-linear", "Score"} <= domains

    def test_default_caption_uses_date(self, one_feature: HRVFeatures) -> None:
        """Default caption includes the session date."""
        styler = table_resting_session(one_feature)
        assert "2024-01-01" in styler.caption

    def test_custom_caption(self, one_feature: HRVFeatures) -> None:
        """Custom caption is applied."""
        styler = table_resting_session(one_feature, caption_text="Custom")
        assert styler.caption == "Custom"

    def test_no_date_fallback_caption(self) -> None:
        """Caption falls back to 'Session detail' when date is None."""
        f = _make_features(date=None)
        styler = table_resting_session(f)
        assert "Session" in styler.caption

    def test_rmssd_value_in_table(self, one_feature: HRVFeatures) -> None:
        """RMSSD value is correctly rendered in the Value cell."""
        styler = table_resting_session(one_feature)
        rmssd_val = styler.data.loc["RMSSD (ms)", "Value"]
        assert "42" in rmssd_val

    def test_score_value_in_table(self, one_feature: HRVFeatures) -> None:
        """Score row contains the numeric value and '/100'."""
        styler = table_resting_session(one_feature)
        score_val = styler.data.loc["HRV Score", "Value"]
        assert "100" in score_val

    def test_dfa_nan_renders_na(self) -> None:
        """NaN DFA α1 renders as 'n/a'."""
        f = _make_features(dfa_alpha1=float("nan"))
        styler = table_resting_session(f)
        dfa_val = styler.data.loc["DFA α1", "Value"]
        assert dfa_val == "n/a"

    def test_wrong_type_raises_type_error(self) -> None:
        """Raise TypeError when input is not HRVFeatures."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            table_resting_session("bad input")
