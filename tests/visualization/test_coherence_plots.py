"""Unit tests for cardiolab.visualization.coherence_plots."""

from __future__ import annotations

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.protocols.cardiac_coherence import (  # noqa: E402
    CoherenceResult,
    cardiac_coherence,
)
from cardiolab.signals.rr import RRSeries  # noqa: E402
from cardiolab.visualization.coherence_plots import (  # noqa: E402
    plot_coherence_psd,
    plot_coherence_score_evolution,
    plot_coherence_tachogram,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_figures():
    """Close all matplotlib figures after each test."""
    yield
    matplotlib.pyplot.close("all")


@pytest.fixture
def rr_coherence() -> RRSeries:
    """Return a 300-interval RRSeries simulating cardiac coherence (0.1 Hz modulation)."""
    rng = np.random.default_rng(42)
    t = np.arange(300) * 0.9  # ~0.9 s per beat → ~67 bpm
    intervals = 900.0 + 80.0 * np.sin(2 * np.pi * 0.1 * t) + rng.normal(0, 5, 300)
    return RRSeries(intervals.clip(min=310).tolist())


@pytest.fixture
def coherence_result(rr_coherence: RRSeries) -> CoherenceResult:
    """Return a CoherenceResult from the coherence fixture RRSeries."""
    return cardiac_coherence(rr_coherence)


@pytest.fixture
def result_good() -> CoherenceResult:
    """Return a CoherenceResult with a good coherence score (≥ 60 %)."""
    return CoherenceResult(
        date="2026-05-18",
        coherence_score=75.0,
        resonance_freq=0.102,
        peak_power=1500.0,
        total_power_resonance=2000.0,
        rmssd=55.0,
        sdnn=80.0,
        mean_hr=62.0,
        duration=300.0,
    )


@pytest.fixture
def result_moderate() -> CoherenceResult:
    """Return a CoherenceResult with a moderate coherence score (40–60 %)."""
    return CoherenceResult(
        date="2026-05-19",
        coherence_score=50.0,
        resonance_freq=0.098,
        peak_power=800.0,
        total_power_resonance=1600.0,
        rmssd=40.0,
        sdnn=65.0,
        mean_hr=65.0,
        duration=300.0,
    )


@pytest.fixture
def result_low() -> CoherenceResult:
    """Return a CoherenceResult with a low coherence score (< 40 %)."""
    return CoherenceResult(
        date="2026-05-20",
        coherence_score=25.0,
        resonance_freq=0.0,
        peak_power=0.0,
        total_power_resonance=0.0,
        rmssd=25.0,
        sdnn=45.0,
        mean_hr=72.0,
        duration=300.0,
    )


@pytest.fixture
def results_multi(
    result_good: CoherenceResult,
    result_moderate: CoherenceResult,
    result_low: CoherenceResult,
) -> list[CoherenceResult]:
    """Return a list of three CoherenceResult entries."""
    return [result_good, result_moderate, result_low]


# ── plot_coherence_psd ────────────────────────────────────────────────────────


class TestPlotCoherencePsd:
    """Tests for plot_coherence_psd."""

    def test_returns_figure(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Normal RRSeries + result: function returns a Figure."""
        fig = plot_coherence_psd(rr_coherence, coherence_result)
        assert isinstance(fig, Figure)

    def test_custom_title(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_coherence_psd(rr_coherence, coherence_result, title="My PSD")
        assert isinstance(fig, Figure)

    def test_custom_figsize(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_coherence_psd(rr_coherence, coherence_result, figsize=(8, 4))
        assert fig.get_size_inches().tolist() == pytest.approx([8.0, 4.0])

    def test_single_axis(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Figure contains exactly one axis."""
        fig = plot_coherence_psd(rr_coherence, coherence_result)
        assert len(fig.axes) == 1

    def test_zero_resonance_freq_accepted(
        self, rr_coherence: RRSeries, result_low: CoherenceResult
    ) -> None:
        """Result with resonance_freq=0 (no peak found): function returns a Figure."""
        fig = plot_coherence_psd(rr_coherence, result_low)
        assert isinstance(fig, Figure)

    def test_rr_not_rrseries_raises(
        self, coherence_result: CoherenceResult
    ) -> None:
        """Non-RRSeries rr raises TypeError."""
        with pytest.raises(TypeError, match="rr must be an RRSeries"):
            plot_coherence_psd([800.0] * 50, coherence_result)  # type: ignore[arg-type]

    def test_rr_too_short_raises(
        self, coherence_result: CoherenceResult
    ) -> None:
        """RRSeries shorter than minimum raises ValueError."""
        with pytest.raises(ValueError, match="at least"):
            plot_coherence_psd(RRSeries([800.0, 820.0]), coherence_result)

    def test_result_wrong_type_raises(self, rr_coherence: RRSeries) -> None:
        """Non-CoherenceResult result raises TypeError."""
        with pytest.raises(TypeError, match="result must be a CoherenceResult"):
            plot_coherence_psd(rr_coherence, {"score": 70})  # type: ignore[arg-type]

    def test_good_score_annotation(
        self, rr_coherence: RRSeries, result_good: CoherenceResult
    ) -> None:
        """Figure with good coherence score is created without raising."""
        fig = plot_coherence_psd(rr_coherence, result_good)
        assert isinstance(fig, Figure)

    def test_custom_resonance_band(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Custom resonance band bounds: function returns a Figure without raising."""
        fig = plot_coherence_psd(
            rr_coherence, coherence_result, resonance_low=0.05, resonance_high=0.20
        )
        assert isinstance(fig, Figure)


# ── plot_coherence_score_evolution ────────────────────────────────────────────


class TestPlotCoherenceScoreEvolution:
    """Tests for plot_coherence_score_evolution."""

    def test_returns_figure_single(self, result_good: CoherenceResult) -> None:
        """Single result: function returns a Figure."""
        fig = plot_coherence_score_evolution([result_good])
        assert isinstance(fig, Figure)

    def test_returns_figure_multi(
        self, results_multi: list[CoherenceResult]
    ) -> None:
        """Three results: function returns a Figure without raising."""
        fig = plot_coherence_score_evolution(results_multi)
        assert isinstance(fig, Figure)

    def test_custom_title(self, results_multi: list[CoherenceResult]) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_coherence_score_evolution(results_multi, title="My Score")
        assert isinstance(fig, Figure)

    def test_custom_labels(self, results_multi: list[CoherenceResult]) -> None:
        """Custom labels: function returns a Figure without raising."""
        labels = ["Lundi", "Mardi", "Mercredi"]
        fig = plot_coherence_score_evolution(results_multi, labels=labels)
        assert isinstance(fig, Figure)

    def test_custom_figsize(self, result_good: CoherenceResult) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_coherence_score_evolution([result_good], figsize=(10, 4))
        assert fig.get_size_inches().tolist() == pytest.approx([10.0, 4.0])

    def test_single_axis(self, results_multi: list[CoherenceResult]) -> None:
        """Figure contains exactly one axis."""
        fig = plot_coherence_score_evolution(results_multi)
        assert len(fig.axes) == 1

    def test_default_labels_from_date(
        self, results_multi: list[CoherenceResult]
    ) -> None:
        """X-axis labels default to the date attribute of each CoherenceResult."""
        fig = plot_coherence_score_evolution(results_multi)
        ax = fig.axes[0]
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        assert "2026-05-18" in tick_labels

    def test_fallback_label_no_date(self) -> None:
        """X-axis falls back to 'Session N' when CoherenceResult.date is None."""
        r = CoherenceResult(date=None, coherence_score=65.0)
        fig = plot_coherence_score_evolution([r])
        ax = fig.axes[0]
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        assert "Session 1" in tick_labels

    def test_results_not_list_raises(self) -> None:
        """Non-list results raises TypeError."""
        with pytest.raises(TypeError, match="results must be a list"):
            plot_coherence_score_evolution("not_a_list")  # type: ignore[arg-type]

    def test_results_empty_raises(self) -> None:
        """Empty results raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_coherence_score_evolution([])

    def test_results_wrong_element_raises(self) -> None:
        """Non-CoherenceResult element raises TypeError."""
        with pytest.raises(TypeError, match="CoherenceResult"):
            plot_coherence_score_evolution([42])  # type: ignore[list-item]

    def test_labels_length_mismatch_raises(
        self, results_multi: list[CoherenceResult]
    ) -> None:
        """Labels list with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_coherence_score_evolution(results_multi, labels=["only one"])


# ── plot_coherence_tachogram ──────────────────────────────────────────────────


class TestPlotCoherenceTachogram:
    """Tests for plot_coherence_tachogram."""

    def test_returns_figure(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Normal session: function returns a Figure."""
        fig = plot_coherence_tachogram(rr_coherence, coherence_result)
        assert isinstance(fig, Figure)

    def test_custom_title(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_coherence_tachogram(rr_coherence, coherence_result, title="Tacho")
        assert isinstance(fig, Figure)

    def test_custom_figsize(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_coherence_tachogram(
            rr_coherence, coherence_result, figsize=(10, 4)
        )
        assert fig.get_size_inches().tolist() == pytest.approx([10.0, 4.0])

    def test_single_axis(
        self, rr_coherence: RRSeries, coherence_result: CoherenceResult
    ) -> None:
        """Figure contains exactly one axis."""
        fig = plot_coherence_tachogram(rr_coherence, coherence_result)
        assert len(fig.axes) == 1

    def test_zero_resonance_freq_no_sine(
        self, rr_coherence: RRSeries, result_low: CoherenceResult
    ) -> None:
        """Result with resonance_freq=0 (no sine drawn): function returns a Figure."""
        fig = plot_coherence_tachogram(rr_coherence, result_low)
        assert isinstance(fig, Figure)

    def test_rr_not_rrseries_raises(
        self, coherence_result: CoherenceResult
    ) -> None:
        """Non-RRSeries rr raises TypeError."""
        with pytest.raises(TypeError, match="rr must be an RRSeries"):
            plot_coherence_tachogram([900.0] * 50, coherence_result)  # type: ignore[arg-type]

    def test_rr_too_short_raises(
        self, coherence_result: CoherenceResult
    ) -> None:
        """RRSeries shorter than minimum raises ValueError."""
        with pytest.raises(ValueError, match="at least"):
            plot_coherence_tachogram(RRSeries([800.0, 820.0]), coherence_result)

    def test_result_wrong_type_raises(self, rr_coherence: RRSeries) -> None:
        """Non-CoherenceResult result raises TypeError."""
        with pytest.raises(TypeError, match="result must be a CoherenceResult"):
            plot_coherence_tachogram(rr_coherence, 42)  # type: ignore[arg-type]

    def test_good_result_with_high_rmssd(self, result_good: CoherenceResult) -> None:
        """Result with high RMSSD and valid resonance_freq: sine overlay is drawn."""
        rng = np.random.default_rng(10)
        t = np.arange(300) * 0.9
        intervals = 900.0 + 80.0 * np.sin(2 * np.pi * 0.1 * t) + rng.normal(0, 5, 300)
        rr = RRSeries(intervals.clip(min=310).tolist())
        fig = plot_coherence_tachogram(rr, result_good)
        assert isinstance(fig, Figure)
