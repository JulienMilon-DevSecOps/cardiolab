"""Unit tests for cardiolab.visualization.rr_plots.

Covers:
- Return type (matplotlib Figure) for every public function.
- Happy-path rendering with realistic RRSeries fixtures.
- Input validation: TypeError on wrong types, ValueError on bad values.
- Edge cases: short series, series with artefacts, optional flags, multi-session.
"""

from __future__ import annotations

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")  # headless backend — no display required

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.signals.rr import RRSeries  # noqa: E402
from cardiolab.visualization.rr_plots import (  # noqa: E402
    plot_rr_comparison,
    plot_rr_distribution,
    plot_rr_filtered,
    plot_rr_summary,
    plot_rr_tachogram,
)

# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def rr_normal() -> RRSeries:
    """RRSeries with 200 intervals at ~70 bpm, reproducible seed."""
    rng = np.random.default_rng(42)
    return RRSeries(rng.normal(857, 25, 200).clip(min=310))


@pytest.fixture
def rr_short() -> RRSeries:
    """Minimal valid RRSeries (2 intervals)."""
    return RRSeries([800.0, 820.0])


@pytest.fixture
def rr_with_artefacts() -> RRSeries:
    """RRSeries containing physiological outliers."""
    rng = np.random.default_rng(0)
    intervals = rng.normal(857, 20, 100).clip(min=310)
    intervals[10] = 2500.0   # above high bound
    intervals[50] = 250.0    # below low bound — triggers PhysiologicalWarning
    return RRSeries(intervals)


@pytest.fixture
def rr_list(rr_normal) -> list[RRSeries]:
    """Three distinct RRSeries for multi-session tests."""
    rng = np.random.default_rng(7)
    s2 = RRSeries(rng.normal(750, 20, 150).clip(min=310))
    s3 = RRSeries(rng.normal(950, 30, 180).clip(min=310))
    return [rr_normal, s2, s3]


# ── plot_rr_tachogram ────────────────────────────────────────────────────────


class TestPlotRrTachogram:
    """Tests for plot_rr_tachogram."""

    def test_returns_figure(self, rr_normal):
        """Function returns a matplotlib Figure."""
        fig = plot_rr_tachogram(rr_normal)
        assert isinstance(fig, Figure)

    def test_short_series(self, rr_short):
        """Works with the minimum valid series length (2 intervals)."""
        fig = plot_rr_tachogram(rr_short)
        assert isinstance(fig, Figure)

    def test_no_mean_no_band_no_hr_axis(self, rr_normal):
        """All optional overlays can be disabled without error."""
        fig = plot_rr_tachogram(
            rr_normal, show_mean=False, show_band=False, show_hr_axis=False
        )
        assert isinstance(fig, Figure)

    def test_custom_title_and_color(self, rr_normal):
        """Custom title and color are accepted."""
        fig = plot_rr_tachogram(rr_normal, title="Test", color="#e74c3c")
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Passing a list instead of RRSeries raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_tachogram([800, 810, 820])

    def test_type_error_on_none(self):
        """Passing None raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_tachogram(None)

    def test_type_error_on_array(self):
        """Passing a raw numpy array raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_tachogram(np.array([800.0, 810.0]))


# ── plot_rr_distribution ─────────────────────────────────────────────────────


class TestPlotRrDistribution:
    """Tests for plot_rr_distribution."""

    def test_returns_figure(self, rr_normal):
        """Function returns a matplotlib Figure."""
        fig = plot_rr_distribution(rr_normal)
        assert isinstance(fig, Figure)

    def test_no_kde_no_stats(self, rr_normal):
        """KDE and stats annotations can both be disabled."""
        fig = plot_rr_distribution(rr_normal, show_kde=False, show_stats=False)
        assert isinstance(fig, Figure)

    def test_kde_skipped_for_short_series(self, rr_short):
        """KDE is silently skipped when fewer than 5 intervals are present."""
        fig = plot_rr_distribution(rr_short, show_kde=True)
        assert isinstance(fig, Figure)

    def test_custom_bins(self, rr_normal):
        """Accepts a custom bin count."""
        fig = plot_rr_distribution(rr_normal, bins=20)
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Wrong type for rr raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_distribution("not_an_rr")

    def test_value_error_bins_zero(self, rr_normal):
        """bins=0 raises ValueError."""
        with pytest.raises(ValueError, match="bins"):
            plot_rr_distribution(rr_normal, bins=0)

    def test_value_error_bins_negative(self, rr_normal):
        """Negative bin count raises ValueError."""
        with pytest.raises(ValueError, match="bins"):
            plot_rr_distribution(rr_normal, bins=-5)


# ── plot_rr_filtered ─────────────────────────────────────────────────────────


class TestPlotRrFiltered:
    """Tests for plot_rr_filtered."""

    def test_returns_figure_auto_filter(self, rr_normal):
        """Auto-filtering (no rr_filtered argument) returns a Figure."""
        fig = plot_rr_filtered(rr_normal)
        assert isinstance(fig, Figure)

    def test_returns_figure_explicit_filtered(self, rr_normal):
        """Pre-filtered series provided explicitly returns a Figure."""
        rr_clean = rr_normal.remove_outliers(method="zscore")
        fig = plot_rr_filtered(rr_normal, rr_filtered=rr_clean)
        assert isinstance(fig, Figure)

    def test_with_artefacts_highlighted(self, rr_with_artefacts):
        """Series containing real outliers renders without error."""
        fig = plot_rr_filtered(rr_with_artefacts)
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Wrong type for rr raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_filtered(42)

    def test_type_error_on_wrong_rr_filtered(self, rr_normal):
        """Wrong type for rr_filtered raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_filtered(rr_normal, rr_filtered=[800, 810])

    def test_value_error_low_zero(self, rr_normal):
        """low=0 raises ValueError."""
        with pytest.raises(ValueError, match="low"):
            plot_rr_filtered(rr_normal, low=0.0, high=2000.0)

    def test_value_error_low_negative(self, rr_normal):
        """Negative low bound raises ValueError."""
        with pytest.raises(ValueError, match="low"):
            plot_rr_filtered(rr_normal, low=-100.0, high=2000.0)

    def test_value_error_low_ge_high(self, rr_normal):
        """Low >= high raises ValueError."""
        with pytest.raises(ValueError, match="low"):
            plot_rr_filtered(rr_normal, low=2000.0, high=300.0)

    def test_value_error_low_equal_high(self, rr_normal):
        """Low == high raises ValueError."""
        with pytest.raises(ValueError, match="low"):
            plot_rr_filtered(rr_normal, low=500.0, high=500.0)


# ── plot_rr_comparison ───────────────────────────────────────────────────────


class TestPlotRrComparison:
    """Tests for plot_rr_comparison."""

    def test_returns_figure_multi(self, rr_list):
        """Multiple sessions return a Figure."""
        fig = plot_rr_comparison(rr_list)
        assert isinstance(fig, Figure)

    def test_single_session(self, rr_normal):
        """A single-element list is accepted."""
        fig = plot_rr_comparison([rr_normal])
        assert isinstance(fig, Figure)

    def test_with_labels(self, rr_list):
        """Custom labels of correct length are accepted."""
        labels = ["Lundi", "Mardi", "Mercredi"]
        fig = plot_rr_comparison(rr_list, labels=labels)
        assert isinstance(fig, Figure)

    def test_normalize_time(self, rr_list):
        """normalize_time=True does not raise."""
        fig = plot_rr_comparison(rr_list, normalize_time=True)
        assert isinstance(fig, Figure)

    def test_value_error_empty_list(self):
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_rr_comparison([])

    def test_type_error_wrong_element(self, rr_normal):
        """Non-RRSeries element raises TypeError with index info."""
        with pytest.raises(TypeError, match=r"rr_list\[1\]"):
            plot_rr_comparison([rr_normal, "bad"])

    def test_value_error_labels_length_mismatch(self, rr_list):
        """Labels with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_rr_comparison(rr_list, labels=["only_one"])

    def test_default_labels_generated(self, rr_list):
        """When labels=None, figure is created with auto-generated labels."""
        fig = plot_rr_comparison(rr_list, labels=None)
        assert isinstance(fig, Figure)


# ── plot_rr_summary ──────────────────────────────────────────────────────────


class TestPlotRrSummary:
    """Tests for plot_rr_summary."""

    def test_returns_figure(self, rr_normal):
        """Function returns a matplotlib Figure."""
        fig = plot_rr_summary(rr_normal)
        assert isinstance(fig, Figure)

    def test_with_artefacts(self, rr_with_artefacts):
        """Series with outliers renders the artefact panel without error."""
        fig = plot_rr_summary(rr_with_artefacts)
        assert isinstance(fig, Figure)

    def test_short_series(self, rr_short):
        """Minimum-length series (2 intervals) renders without error."""
        fig = plot_rr_summary(rr_short)
        assert isinstance(fig, Figure)

    def test_custom_title(self, rr_normal):
        """Custom title is accepted."""
        fig = plot_rr_summary(rr_normal, title="Session 2026-05-20")
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Passing a dict instead of RRSeries raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_summary({"rr": [800, 810]})

    def test_type_error_on_none(self):
        """Passing None raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_rr_summary(None)
