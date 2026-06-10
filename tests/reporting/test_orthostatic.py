"""Tests for cardiolab.reporting.orthostatic."""

from __future__ import annotations

import numpy as np
import pytest
from pandas.io.formats.style import Styler

from cardiolab.labels import LABELS_EN, LABELS_FR
from cardiolab.protocols.orthostatic import (
    OrthostaticPhases,
    OrthostaticResult,
    PhaseSegment,
    TransitionSegment,
)
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.reporting.orthostatic import (
    _validate_list,
    table_orthostatic_comparison,
    table_orthostatic_history,
)
from cardiolab.signals.rr import RRSeries

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_features(**kwargs) -> HRVFeatures:
    """Build an HRVFeatures instance with sensible defaults."""
    defaults = dict(
        rmssd=40.0,
        ln_rmssd=3.69,
        sdnn=50.0,
        pnn50=25.0,
        mean_hr=62.0,
        vlf=150.0,
        lf=400.0,
        hf=700.0,
        lf_hf=0.57,
        hf_pct=0.52,
        lf_nu=0.36,
        hf_nu=0.60,
        sd1=28.0,
        sd2=65.0,
        sd_ratio=0.43,
        dfa_alpha1=1.0,
        apen=1.1,
        sampen=1.2,
        score=68.0,
        method="welch",
    )
    defaults.update(kwargs)
    return HRVFeatures(**defaults)


def _make_rr() -> RRSeries:
    """Build a minimal RRSeries (300 × 1000 ms)."""
    return RRSeries(intervals=np.full(300, 1000.0))


def _make_phase(mean_hr: float = 62.0) -> PhaseSegment:
    """Build a PhaseSegment with the given mean HR."""
    return PhaseSegment(
        rr=_make_rr(),
        start_sec=0.0,
        end_sec=300.0,
        duration_sec=300.0,
        features=_make_features(mean_hr=mean_hr),
    )


def _make_transition() -> TransitionSegment:
    """Build a TransitionSegment."""
    return TransitionSegment(
        rr=_make_rr(),
        start_sec=300.0,
        end_sec=360.0,
        duration_sec=60.0,
        delta_hr=15.0,
        peak_hr=85.0,
        features=_make_features(mean_hr=80.0),
    )


def _make_result(interpretation: str = "normal") -> OrthostaticResult:
    """Build an OrthostaticResult with a given interpretation."""
    return OrthostaticResult(
        phases=OrthostaticPhases(
            supine=_make_phase(mean_hr=60.0),
            transition=_make_transition(),
            standing=_make_phase(mean_hr=75.0),
        ),
        hr_response=15.0,
        lf_hf_ratio_change=1.4,
        hf_response_pct=35.0,
        hf_hr_pct_change=55.0,
        lf_hr_pct_change=30.0,
        delta_rmssd=18.0,
        interpretation=interpretation,
    )


@pytest.fixture
def one_result() -> OrthostaticResult:
    """Single OrthostaticResult session."""
    return _make_result()


@pytest.fixture
def two_results() -> list[OrthostaticResult]:
    """Two OrthostaticResult sessions with different interpretations."""
    return [_make_result("normal"), _make_result("impaired")]


# ── _validate_list ────────────────────────────────────────────────────────────


def test_validate_list_not_a_list() -> None:
    """Raise TypeError when argument is not a list."""
    with pytest.raises(TypeError, match="must be a list"):
        _validate_list("not a list", OrthostaticResult, "results")


def test_validate_list_empty() -> None:
    """Raise ValueError when list is empty."""
    with pytest.raises(ValueError, match="at least one element"):
        _validate_list([], OrthostaticResult, "results")


def test_validate_list_wrong_type(one_result: OrthostaticResult) -> None:
    """Raise TypeError when an element has the wrong type."""
    with pytest.raises(TypeError, match="results\\[1\\]"):
        _validate_list([one_result, "bad"], OrthostaticResult, "results")


def test_validate_list_ok(one_result: OrthostaticResult) -> None:
    """Pass silently for a valid single-element list."""
    _validate_list([one_result], OrthostaticResult, "results")


# ── table_orthostatic_comparison ──────────────────────────────────────────────


class TestTableOrthostaticComparison:
    """Tests for table_orthostatic_comparison."""

    def test_returns_styler(self, two_results: list[OrthostaticResult]) -> None:
        """Return a pandas Styler."""
        styler = table_orthostatic_comparison(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: OrthostaticResult) -> None:
        """One-row table for a single session."""
        styler = table_orthostatic_comparison([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[OrthostaticResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_orthostatic_comparison(two_results)
        assert len(styler.data) == 2

    def test_supine_standing_columns_present(
        self, one_result: OrthostaticResult
    ) -> None:
        """Supine and standing RMSSD/HR columns exist under MultiIndex."""
        styler = table_orthostatic_comparison([one_result])
        cols = set(styler.data.columns)
        assert ("Supine", "rmssd") in cols
        assert ("Standing", "rmssd") in cols
        assert ("Supine", "mean_hr") in cols
        assert ("Standing", "mean_hr") in cols

    def test_delta_columns_present(self, one_result: OrthostaticResult) -> None:
        """Response columns and interpretation are present under MultiIndex."""
        styler = table_orthostatic_comparison([one_result])
        cols = set(styler.data.columns)
        for col in (
            ("Autonomic response", "hr_response"),
            ("Autonomic response", "lf_hf_change"),
            ("Autonomic response", "hf_response_pct"),
            ("Autonomic response", "hf_hr_pct_change"),
            ("Autonomic response", "interpretation"),
        ):
            assert col in cols

    def test_custom_dates(self, two_results: list[OrthostaticResult]) -> None:
        """Custom date labels appear as DataFrame index."""
        dates = ["2024-01-01", "2024-01-08"]
        styler = table_orthostatic_comparison(two_results, dates=dates)
        assert list(styler.data.index) == dates

    def test_default_dates_fallback(self, two_results: list[OrthostaticResult]) -> None:
        """Default date labels follow 'Session N' pattern in the index."""
        styler = table_orthostatic_comparison(two_results)
        assert styler.data.index[0] == "Session 1"
        assert styler.data.index[1] == "Session 2"

    def test_dates_length_mismatch_raises(
        self, two_results: list[OrthostaticResult]
    ) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_orthostatic_comparison(two_results, dates=["only one"])

    def test_caption(self, one_result: OrthostaticResult) -> None:
        """Custom caption is applied."""
        styler = table_orthostatic_comparison([one_result], caption_text="Test caption")
        assert styler.caption == "Test caption"

    def test_hr_response_value(self, one_result: OrthostaticResult) -> None:
        """HR response value is stored correctly."""
        styler = table_orthostatic_comparison([one_result])
        assert (
            pytest.approx(
                styler.data[("Autonomic response", "hr_response")].iloc[0], rel=1e-3
            )
            == 15.0
        )

    def test_interpretation_value(self, one_result: OrthostaticResult) -> None:
        """Interpretation string is stored correctly."""
        styler = table_orthostatic_comparison([one_result])
        assert styler.data[("Autonomic response", "interpretation")].iloc[0] == "normal"

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_orthostatic_comparison("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_orthostatic_comparison([])

    def test_nan_dfa_columns(self) -> None:
        """NaN values in DFA columns do not crash."""
        r = _make_result()
        r.phases.supine.features.dfa_alpha1 = float("nan")
        r.phases.standing.features.dfa_alpha1 = float("nan")
        styler = table_orthostatic_comparison([r])
        assert styler is not None

    def test_lf_hf_change_value(self, one_result: OrthostaticResult) -> None:
        """LF/HF change value is stored correctly."""
        styler = table_orthostatic_comparison([one_result])
        assert (
            pytest.approx(
                styler.data[("Autonomic response", "lf_hf_change")].iloc[0], rel=1e-3
            )
            == 1.4
        )

    def test_interpretation_categories(
        self, two_results: list[OrthostaticResult]
    ) -> None:
        """Both 'normal' and 'impaired' interpretations appear in the table."""
        styler = table_orthostatic_comparison(two_results)
        interps = list(styler.data[("Autonomic response", "interpretation")])
        assert "normal" in interps
        assert "impaired" in interps


# ── table_orthostatic_history ─────────────────────────────────────────────────


class TestTableOrthostaticHistory:
    """Tests for table_orthostatic_history."""

    def test_returns_styler(self, two_results: list[OrthostaticResult]) -> None:
        """Return a pandas Styler."""
        styler = table_orthostatic_history(two_results)
        assert isinstance(styler, Styler)

    def test_single_session(self, one_result: OrthostaticResult) -> None:
        """One-row table for a single session."""
        styler = table_orthostatic_history([one_result])
        assert len(styler.data) == 1

    def test_two_sessions(self, two_results: list[OrthostaticResult]) -> None:
        """Two-row table for two sessions."""
        styler = table_orthostatic_history(two_results)
        assert len(styler.data) == 2

    def test_key_columns_present(self, one_result: OrthostaticResult) -> None:
        """All condensed history columns are present."""
        styler = table_orthostatic_history([one_result])
        cols = set(styler.data.columns)
        for col in (
            "supine_rmssd",
            "standing_rmssd",
            "supine_hr",
            "standing_hr",
            "hr_response",
            "lf_hf_change",
            "hf_response_pct",
            "hf_hr_pct_change",
            "interpretation",
        ):
            assert col in cols, f"missing column: {col}"

    def test_custom_dates(self, two_results: list[OrthostaticResult]) -> None:
        """Custom date labels appear in the date column."""
        dates = ["Semaine 1", "Semaine 2"]
        styler = table_orthostatic_history(two_results, dates=dates)
        assert list(styler.data["date"]) == dates

    def test_default_dates_fallback(self, two_results: list[OrthostaticResult]) -> None:
        """Default date labels follow 'Session N' pattern."""
        styler = table_orthostatic_history(two_results)
        assert styler.data["date"].iloc[0] == "Session 1"

    def test_dates_length_mismatch_raises(
        self, two_results: list[OrthostaticResult]
    ) -> None:
        """Raise ValueError when dates length mismatches results length."""
        with pytest.raises(ValueError, match="dates length"):
            table_orthostatic_history(two_results, dates=["only one"])

    def test_caption(self, one_result: OrthostaticResult) -> None:
        """Custom caption is applied."""
        styler = table_orthostatic_history([one_result], caption_text="Custom")
        assert styler.caption == "Custom"

    def test_supine_rmssd_value(self, one_result: OrthostaticResult) -> None:
        """Supine RMSSD value is stored correctly."""
        styler = table_orthostatic_history([one_result])
        assert pytest.approx(styler.data["supine_rmssd"].iloc[0], rel=1e-3) == 40.0

    def test_standing_hr_value(self, one_result: OrthostaticResult) -> None:
        """Standing HR value is stored correctly."""
        styler = table_orthostatic_history([one_result])
        assert pytest.approx(styler.data["standing_hr"].iloc[0], rel=1e-3) == 75.0

    def test_not_a_list_raises(self) -> None:
        """Raise TypeError when input is not a list."""
        with pytest.raises(TypeError):
            table_orthostatic_history("not a list")

    def test_empty_list_raises(self) -> None:
        """Raise ValueError when list is empty."""
        with pytest.raises(ValueError):
            table_orthostatic_history([])

    def test_interpretation_in_history(self, one_result: OrthostaticResult) -> None:
        """Interpretation is stored in the condensed history table."""
        styler = table_orthostatic_history([one_result])
        assert styler.data["interpretation"].iloc[0] == "normal"


class TestDualScoreColumnsComparison:
    """Tests for readiness_scores integration in table_orthostatic_comparison."""

    def test_dual_score_columns_added(self, one_result: OrthostaticResult) -> None:
        """readiness_score and autonomic_score columns appear when scores provided."""
        styler = table_orthostatic_comparison(
            [one_result], readiness_scores=[62.0]
        )
        flat_cols = [c[1] for c in styler.data.columns]
        assert "readiness_score" in flat_cols
        assert "autonomic_score" in flat_cols

    def test_readiness_score_value_stored(self, one_result: OrthostaticResult) -> None:
        """readiness_score value round-trips correctly through the table."""
        one_result.score = 70.0
        styler = table_orthostatic_comparison(
            [one_result], readiness_scores=[58.0]
        )
        mi_col = ("Autonomic response", "readiness_score")
        assert styler.data[mi_col].iloc[0] == pytest.approx(58.0)

    def test_readiness_label_key_stored(self, one_result: OrthostaticResult) -> None:
        """readiness_label internal key is correct for score = 62 (good_recovery zone)."""
        styler = table_orthostatic_comparison(
            [one_result], readiness_scores=[62.0]
        )
        mi_col = ("Autonomic response", "readiness_label")
        assert styler.data[mi_col].iloc[0] == "good_recovery"

    def test_readiness_scores_length_mismatch_raises(
        self, two_results: list[OrthostaticResult]
    ) -> None:
        """Raise ValueError when readiness_scores length mismatches results."""
        with pytest.raises(ValueError, match="readiness_scores length"):
            table_orthostatic_comparison(two_results, readiness_scores=[50.0])

    def test_with_labels_fr_accepted(self, one_result: OrthostaticResult) -> None:
        """labels=LABELS_FR is accepted without error."""
        styler = table_orthostatic_comparison(
            [one_result], readiness_scores=[62.0], labels=LABELS_FR
        )
        assert isinstance(styler, __import__("pandas.io.formats.style", fromlist=["Styler"]).Styler)

    def test_with_labels_en_accepted(self, one_result: OrthostaticResult) -> None:
        """labels=LABELS_EN is accepted without error."""
        styler = table_orthostatic_comparison(
            [one_result], readiness_scores=[62.0], labels=LABELS_EN
        )
        from pandas.io.formats.style import Styler
        assert isinstance(styler, Styler)

    def test_without_readiness_scores_no_crash(
        self, one_result: OrthostaticResult
    ) -> None:
        """Calling without readiness_scores still produces a valid Styler."""
        from pandas.io.formats.style import Styler
        styler = table_orthostatic_comparison([one_result])
        assert isinstance(styler, Styler)


class TestDualScoreColumnsHistory:
    """Tests for readiness_scores integration in table_orthostatic_history."""

    def test_dual_score_columns_added(self, one_result: OrthostaticResult) -> None:
        """readiness_score and readiness_label columns appear when scores provided."""
        styler = table_orthostatic_history([one_result], readiness_scores=[58.0])
        cols = set(styler.data.columns)
        assert "readiness_score" in cols
        assert "readiness_label" in cols
        assert "autonomic_label" in cols

    def test_readiness_score_value_stored(self, one_result: OrthostaticResult) -> None:
        """readiness_score value round-trips correctly through the history table."""
        styler = table_orthostatic_history([one_result], readiness_scores=[72.0])
        assert styler.data["readiness_score"].iloc[0] == pytest.approx(72.0)

    def test_readiness_label_key_for_high_score(
        self, one_result: OrthostaticResult
    ) -> None:
        """Score ≥ 65 → readiness_label = 'excellent'."""
        styler = table_orthostatic_history([one_result], readiness_scores=[68.0])
        assert styler.data["readiness_label"].iloc[0] == "excellent"

    def test_readiness_label_key_for_low_score(
        self, one_result: OrthostaticResult
    ) -> None:
        """Score < 35 → readiness_label = 'high_fatigue'."""
        styler = table_orthostatic_history([one_result], readiness_scores=[20.0])
        assert styler.data["readiness_label"].iloc[0] == "high_fatigue"

    def test_readiness_scores_length_mismatch_raises(
        self, two_results: list[OrthostaticResult]
    ) -> None:
        """Raise ValueError when readiness_scores length mismatches results."""
        with pytest.raises(ValueError, match="readiness_scores length"):
            table_orthostatic_history(two_results, readiness_scores=[50.0])

    def test_with_labels_fr_accepted(self, one_result: OrthostaticResult) -> None:
        """labels=LABELS_FR is accepted without error."""
        from pandas.io.formats.style import Styler
        styler = table_orthostatic_history(
            [one_result], readiness_scores=[62.0], labels=LABELS_FR
        )
        assert isinstance(styler, Styler)

    def test_without_readiness_scores_no_crash(
        self, one_result: OrthostaticResult
    ) -> None:
        """Calling without readiness_scores still produces a valid Styler."""
        from pandas.io.formats.style import Styler
        styler = table_orthostatic_history([one_result])
        assert isinstance(styler, Styler)
