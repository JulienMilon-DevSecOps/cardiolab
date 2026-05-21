"""Unit tests for cardiolab.visualization.resting_plots."""

from __future__ import annotations

import math

import matplotlib
import pytest

matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.protocols.resting import HRVFeatures  # noqa: E402
from cardiolab.visualization.resting_plots import (  # noqa: E402
    plot_resting_evolution,
    plot_resting_evolution_rolling,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_figures():
    """Close all matplotlib figures after each test."""
    yield
    matplotlib.pyplot.close("all")


def _make_features(
    rmssd: float = 55.0,
    date: str | None = "2026-05-18",
) -> HRVFeatures:
    """Return a minimal HRVFeatures instance with plausible values."""
    return HRVFeatures(
        rmssd=rmssd,
        ln_rmssd=math.log(rmssd),
        sdnn=70.0,
        pnn50=0.28,
        mean_hr=62.0,
        vlf=300.0,
        lf=500.0,
        hf=400.0,
        lf_hf=1.25,
        hf_pct=0.33,
        lf_nu=0.55,
        hf_nu=0.45,
        hf_hr=0.0,
        sd1=35.0,
        sd2=90.0,
        sd_ratio=2.57,
        dfa_alpha1=1.1,
        apen=1.2,
        sampen=1.3,
        duration=300.0,
        score=75.0,
        method="welch",
        date=date,
    )


@pytest.fixture
def single_feature() -> list[HRVFeatures]:
    """List with one HRVFeatures entry."""
    return [_make_features(rmssd=55.0, date="2026-05-18")]


@pytest.fixture
def multi_features() -> list[HRVFeatures]:
    """List with three HRVFeatures entries."""
    return [
        _make_features(rmssd=55.0, date="2026-05-18"),
        _make_features(rmssd=62.0, date="2026-05-19"),
        _make_features(rmssd=48.0, date="2026-05-20"),
    ]


@pytest.fixture
def single_score() -> list[float]:
    """Readiness score list matching single_feature."""
    return [72.0]


@pytest.fixture
def multi_scores() -> list[float]:
    """Readiness score list matching multi_features."""
    return [72.0, 80.0, 61.0]


@pytest.fixture
def multi_rolling() -> list[float | None]:
    """Return rolling RMSSD medians matching multi_features (first entry is None)."""
    return [None, 55.0, 58.5]


# ── plot_resting_evolution ────────────────────────────────────────────────────


class TestPlotRestingEvolution:
    """Tests for plot_resting_evolution."""

    def test_returns_figure(
        self, single_feature: list[HRVFeatures], single_score: list[float]
    ) -> None:
        """Single session: function returns a Figure."""
        fig = plot_resting_evolution(single_feature, single_score)
        assert isinstance(fig, Figure)

    def test_multiple_sessions(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Three sessions: function returns a Figure without raising."""
        fig = plot_resting_evolution(multi_features, multi_scores)
        assert isinstance(fig, Figure)

    def test_custom_title(
        self, single_feature: list[HRVFeatures], single_score: list[float]
    ) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_resting_evolution(single_feature, single_score, title="My Title")
        assert isinstance(fig, Figure)

    def test_custom_labels(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Custom labels: function returns a Figure without raising."""
        labels = ["Day 1", "Day 2", "Day 3"]
        fig = plot_resting_evolution(multi_features, multi_scores, labels=labels)
        assert isinstance(fig, Figure)

    def test_custom_figsize(
        self, single_feature: list[HRVFeatures], single_score: list[float]
    ) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_resting_evolution(single_feature, single_score, figsize=(8, 5))
        assert fig.get_size_inches().tolist() == pytest.approx([8.0, 5.0])

    def test_two_axes(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Figure contains exactly two axes (RMSSD + readiness score panels)."""
        fig = plot_resting_evolution(multi_features, multi_scores)
        assert len(fig.axes) == 2

    def test_features_list_not_list_raises(self, single_score: list[float]) -> None:
        """Non-list features_list raises TypeError."""
        with pytest.raises(TypeError, match="features_list must be a list"):
            plot_resting_evolution("not_a_list", single_score)  # type: ignore[arg-type]

    def test_features_list_empty_raises(self, single_score: list[float]) -> None:
        """Empty features_list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_resting_evolution([], single_score)

    def test_features_list_wrong_element_raises(
        self, single_score: list[float]
    ) -> None:
        """Non-HRVFeatures element raises TypeError."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_resting_evolution([42], single_score)  # type: ignore[list-item]

    def test_scores_not_list_raises(
        self, single_feature: list[HRVFeatures]
    ) -> None:
        """Non-list scores raises TypeError."""
        with pytest.raises(TypeError, match="scores must be a list"):
            plot_resting_evolution(single_feature, 72.0)  # type: ignore[arg-type]

    def test_scores_length_mismatch_raises(
        self, multi_features: list[HRVFeatures]
    ) -> None:
        """Scores list shorter than features_list raises ValueError."""
        with pytest.raises(ValueError, match="scores length"):
            plot_resting_evolution(multi_features, [72.0])

    def test_labels_length_mismatch_raises(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Labels list with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_resting_evolution(multi_features, multi_scores, labels=["only one"])

    def test_default_labels_from_date(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """X-axis tick labels default to the date attribute of each HRVFeatures."""
        fig = plot_resting_evolution(multi_features, multi_scores)
        ax_score = fig.axes[1]
        tick_labels = [t.get_text() for t in ax_score.get_xticklabels()]
        assert "2026-05-18" in tick_labels

    def test_fallback_labels_no_date(self, single_score: list[float]) -> None:
        """X-axis falls back to 'Session N' when HRVFeatures.date is None."""
        feature_no_date = _make_features(date=None)
        fig = plot_resting_evolution([feature_no_date], single_score)
        ax_score = fig.axes[1]
        tick_labels = [t.get_text() for t in ax_score.get_xticklabels()]
        assert "Session 1" in tick_labels


# ── plot_resting_evolution_rolling ───────────────────────────────────────────


class TestPlotRestingEvolutionRolling:
    """Tests for plot_resting_evolution_rolling."""

    def test_returns_figure(
        self,
        single_feature: list[HRVFeatures],
        single_score: list[float],
    ) -> None:
        """Single session with None rolling: function returns a Figure."""
        fig = plot_resting_evolution_rolling(single_feature, single_score, [None])
        assert isinstance(fig, Figure)

    def test_multiple_sessions(
        self,
        multi_features: list[HRVFeatures],
        multi_scores: list[float],
        multi_rolling: list[float | None],
    ) -> None:
        """Three sessions with rolling median: function returns a Figure."""
        fig = plot_resting_evolution_rolling(
            multi_features, multi_scores, multi_rolling
        )
        assert isinstance(fig, Figure)

    def test_custom_title(
        self,
        single_feature: list[HRVFeatures],
        single_score: list[float],
    ) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_resting_evolution_rolling(
            single_feature, single_score, [None], title="Rolling Test"
        )
        assert isinstance(fig, Figure)

    def test_custom_labels(
        self,
        multi_features: list[HRVFeatures],
        multi_scores: list[float],
        multi_rolling: list[float | None],
    ) -> None:
        """Custom labels: function returns a Figure without raising."""
        labels = ["D1", "D2", "D3"]
        fig = plot_resting_evolution_rolling(
            multi_features, multi_scores, multi_rolling, labels=labels
        )
        assert isinstance(fig, Figure)

    def test_custom_figsize(
        self,
        single_feature: list[HRVFeatures],
        single_score: list[float],
    ) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_resting_evolution_rolling(
            single_feature, single_score, [None], figsize=(10, 6)
        )
        assert fig.get_size_inches().tolist() == pytest.approx([10.0, 6.0])

    def test_two_axes(
        self,
        multi_features: list[HRVFeatures],
        multi_scores: list[float],
        multi_rolling: list[float | None],
    ) -> None:
        """Figure contains exactly two axes (RMSSD+rolling top, score bottom)."""
        fig = plot_resting_evolution_rolling(
            multi_features, multi_scores, multi_rolling
        )
        assert len(fig.axes) == 2

    def test_none_rolling_accepted(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """All-None rolling_rmssd: function returns a Figure without raising."""
        rolling_all_none: list[float | None] = [None, None, None]
        fig = plot_resting_evolution_rolling(
            multi_features, multi_scores, rolling_all_none
        )
        assert isinstance(fig, Figure)

    def test_features_list_not_list_raises(self, multi_scores: list[float]) -> None:
        """Non-list features_list raises TypeError."""
        with pytest.raises(TypeError, match="features_list must be a list"):
            plot_resting_evolution_rolling("x", multi_scores, [1.0, 2.0, 3.0])  # type: ignore[arg-type]

    def test_features_list_empty_raises(self, multi_scores: list[float]) -> None:
        """Empty features_list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_resting_evolution_rolling([], multi_scores, [])

    def test_scores_not_list_raises(
        self, multi_features: list[HRVFeatures], multi_rolling: list[float | None]
    ) -> None:
        """Non-list scores raises TypeError."""
        with pytest.raises(TypeError, match="scores must be a list"):
            plot_resting_evolution_rolling(multi_features, 72.0, multi_rolling)  # type: ignore[arg-type]

    def test_rolling_not_list_raises(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Non-list rolling_rmssd raises TypeError."""
        with pytest.raises(TypeError, match="rolling_rmssd must be a list"):
            plot_resting_evolution_rolling(multi_features, multi_scores, 55.0)  # type: ignore[arg-type]

    def test_scores_length_mismatch_raises(
        self, multi_features: list[HRVFeatures], multi_rolling: list[float | None]
    ) -> None:
        """Scores list shorter than features_list raises ValueError."""
        with pytest.raises(ValueError, match="scores length"):
            plot_resting_evolution_rolling(multi_features, [72.0], multi_rolling)

    def test_rolling_length_mismatch_raises(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """Rolling list shorter than features_list raises ValueError."""
        with pytest.raises(ValueError, match="rolling_rmssd length"):
            plot_resting_evolution_rolling(multi_features, multi_scores, [55.0])

    def test_labels_length_mismatch_raises(
        self,
        multi_features: list[HRVFeatures],
        multi_scores: list[float],
        multi_rolling: list[float | None],
    ) -> None:
        """Labels list with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_resting_evolution_rolling(
                multi_features, multi_scores, multi_rolling, labels=["only one"]
            )

    def test_rmssd_values_finite(
        self, multi_features: list[HRVFeatures]
    ) -> None:
        """All RMSSD values in the fixture are finite (no NaN or Inf)."""
        for f in multi_features:
            assert math.isfinite(f.rmssd)

    def test_score_range(self, multi_scores: list[float]) -> None:
        """All fixture scores are within the expected 0–100 range."""
        for s in multi_scores:
            assert 0.0 <= s <= 100.0

    def test_rolling_nan_gap_accepted(
        self, multi_features: list[HRVFeatures], multi_scores: list[float]
    ) -> None:
        """None in rolling_rmssd is plotted as a gap without raising."""
        rolling: list[float | None] = [None, 55.0, 58.5]
        fig = plot_resting_evolution_rolling(multi_features, multi_scores, rolling)
        assert isinstance(fig, Figure)
