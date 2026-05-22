"""Unit tests for cardiolab.visualization.nonlinear_plots."""

from __future__ import annotations

import math

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.protocols.resting import HRVFeatures  # noqa: E402
from cardiolab.signals.rr import RRSeries  # noqa: E402
from cardiolab.visualization.nonlinear_plots import (  # noqa: E402
    plot_poincare,
    plot_poincare_comparison,
    plot_sd1_sd2_evolution,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_figures():
    """Close all matplotlib figures after each test."""
    yield
    matplotlib.pyplot.close("all")


@pytest.fixture
def rr_normal() -> RRSeries:
    """Return a 300-interval RRSeries with normal resting variability."""
    rng = np.random.default_rng(42)
    return RRSeries(rng.normal(860, 40, 300).clip(min=310).tolist())


@pytest.fixture
def rr_standing() -> RRSeries:
    """Return a 300-interval RRSeries simulating standing (lower mean HR, lower variability)."""
    rng = np.random.default_rng(7)
    return RRSeries(rng.normal(720, 20, 300).clip(min=310).tolist())


@pytest.fixture
def rr_minimal() -> RRSeries:
    """Return the smallest valid RRSeries (3 intervals)."""
    return RRSeries([800.0, 820.0, 790.0])


def _make_features(
    sd1: float = 35.0,
    sd2: float = 80.0,
    sd_ratio: float = 0.44,
    date: str | None = "2026-05-18",
) -> HRVFeatures:
    """Return a minimal HRVFeatures instance with plausible non-linear values."""
    return HRVFeatures(
        rmssd=sd1 * math.sqrt(2),
        ln_rmssd=math.log(sd1 * math.sqrt(2)),
        sdnn=70.0,
        pnn50=0.25,
        mean_hr=62.0,
        vlf=300.0,
        lf=500.0,
        hf=400.0,
        lf_hf=1.25,
        hf_pct=0.33,
        lf_nu=0.55,
        hf_nu=0.45,
        hf_hr=0.0,
        sd1=sd1,
        sd2=sd2,
        sd_ratio=sd_ratio,
        dfa_alpha1=1.1,
        apen=1.2,
        sampen=1.3,
        duration=300.0,
        score=75.0,
        method="welch",
        date=date,
    )


@pytest.fixture
def features_single() -> list[HRVFeatures]:
    """List with one HRVFeatures entry."""
    return [_make_features(sd1=35.0, sd2=80.0, date="2026-05-18")]


@pytest.fixture
def features_multi() -> list[HRVFeatures]:
    """List with three HRVFeatures entries."""
    return [
        _make_features(sd1=35.0, sd2=80.0, date="2026-05-18"),
        _make_features(sd1=40.0, sd2=85.0, sd_ratio=0.47, date="2026-05-19"),
        _make_features(sd1=28.0, sd2=75.0, sd_ratio=0.37, date="2026-05-20"),
    ]


@pytest.fixture
def features_nan_ratio() -> list[HRVFeatures]:
    """List with one entry where sd_ratio is NaN (forced edge case)."""
    return [_make_features(sd1=35.0, sd2=80.0, sd_ratio=float("nan"), date="2026-05-21")]


# ── plot_poincare ─────────────────────────────────────────────────────────────


class TestPlotPoincare:
    """Tests for plot_poincare."""

    def test_returns_figure(self, rr_normal: RRSeries) -> None:
        """Normal RRSeries: function returns a Figure."""
        fig = plot_poincare(rr_normal)
        assert isinstance(fig, Figure)

    def test_minimal_series(self, rr_minimal: RRSeries) -> None:
        """Three-interval series (minimum): function returns a Figure."""
        fig = plot_poincare(rr_minimal)
        assert isinstance(fig, Figure)

    def test_custom_title(self, rr_normal: RRSeries) -> None:
        """Custom title: figure is created without raising."""
        fig = plot_poincare(rr_normal, title="Test Title")
        assert isinstance(fig, Figure)

    def test_custom_figsize(self, rr_normal: RRSeries) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_poincare(rr_normal, figsize=(8, 8))
        assert fig.get_size_inches().tolist() == pytest.approx([8.0, 8.0])

    def test_single_axis(self, rr_normal: RRSeries) -> None:
        """Figure contains exactly one axis."""
        fig = plot_poincare(rr_normal)
        assert len(fig.axes) == 1

    def test_rr_not_rrseries_raises(self) -> None:
        """Non-RRSeries input raises TypeError."""
        with pytest.raises(TypeError, match="rr must be an RRSeries"):
            plot_poincare([800.0, 820.0, 790.0])  # type: ignore[arg-type]

    def test_rr_too_short_raises(self) -> None:
        """Series shorter than minimum raises ValueError."""
        with pytest.raises(ValueError, match="at least"):
            plot_poincare(RRSeries([800.0, 820.0]))

    def test_equal_aspect(self, rr_normal: RRSeries) -> None:
        """Plot axis has an equal aspect ratio (square Poincaré scatter)."""
        fig = plot_poincare(rr_normal)
        ax = fig.axes[0]
        # matplotlib stores "equal" as 1.0 after tight_layout
        assert ax.get_aspect() in ("equal", pytest.approx(1.0))

    def test_ellipse_present(self, rr_normal: RRSeries) -> None:
        """Figure axis contains at least one Ellipse patch (SD1/SD2 ellipse)."""
        from matplotlib.patches import Ellipse

        fig = plot_poincare(rr_normal)
        ax = fig.axes[0]
        ellipses = [p for p in ax.patches if isinstance(p, Ellipse)]
        assert len(ellipses) >= 1


# ── plot_poincare_comparison ──────────────────────────────────────────────────


class TestPlotPoincareComparison:
    """Tests for plot_poincare_comparison."""

    def test_returns_figure(
        self, rr_normal: RRSeries, rr_standing: RRSeries
    ) -> None:
        """Two valid RRSeries: function returns a Figure."""
        fig = plot_poincare_comparison(rr_normal, rr_standing)
        assert isinstance(fig, Figure)

    def test_two_axes(self, rr_normal: RRSeries, rr_standing: RRSeries) -> None:
        """Figure contains exactly two axes (supine + standing panels)."""
        fig = plot_poincare_comparison(rr_normal, rr_standing)
        assert len(fig.axes) == 2

    def test_custom_labels(
        self, rr_normal: RRSeries, rr_standing: RRSeries
    ) -> None:
        """Custom panel labels: figure is created without raising."""
        fig = plot_poincare_comparison(
            rr_normal, rr_standing,
            label_supine="Allongé", label_standing="Debout",
        )
        assert isinstance(fig, Figure)

    def test_custom_title(self, rr_normal: RRSeries, rr_standing: RRSeries) -> None:
        """Custom overall title: figure is created without raising."""
        fig = plot_poincare_comparison(rr_normal, rr_standing, title="My Test")
        assert isinstance(fig, Figure)

    def test_custom_figsize(
        self, rr_normal: RRSeries, rr_standing: RRSeries
    ) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_poincare_comparison(rr_normal, rr_standing, figsize=(10, 5))
        assert fig.get_size_inches().tolist() == pytest.approx([10.0, 5.0])

    def test_shared_xlim(self, rr_normal: RRSeries, rr_standing: RRSeries) -> None:
        """Both panels share the same x-axis limits for direct comparison."""
        fig = plot_poincare_comparison(rr_normal, rr_standing)
        ax1, ax2 = fig.axes
        assert ax1.get_xlim() == pytest.approx(ax2.get_xlim())

    def test_shared_ylim(self, rr_normal: RRSeries, rr_standing: RRSeries) -> None:
        """Both panels share the same y-axis limits for direct comparison."""
        fig = plot_poincare_comparison(rr_normal, rr_standing)
        ax1, ax2 = fig.axes
        assert ax1.get_ylim() == pytest.approx(ax2.get_ylim())

    def test_supine_not_rrseries_raises(
        self, rr_standing: RRSeries
    ) -> None:
        """Non-RRSeries supine argument raises TypeError."""
        with pytest.raises(TypeError, match="rr must be an RRSeries"):
            plot_poincare_comparison("not_rr", rr_standing)  # type: ignore[arg-type]

    def test_standing_not_rrseries_raises(
        self, rr_normal: RRSeries
    ) -> None:
        """Non-RRSeries standing argument raises TypeError."""
        with pytest.raises(TypeError, match="rr must be an RRSeries"):
            plot_poincare_comparison(rr_normal, "not_rr")  # type: ignore[arg-type]

    def test_supine_too_short_raises(self, rr_standing: RRSeries) -> None:
        """Supine series shorter than minimum raises ValueError."""
        with pytest.raises(ValueError, match="at least"):
            plot_poincare_comparison(RRSeries([800.0]), rr_standing)

    def test_ellipses_present(
        self, rr_normal: RRSeries, rr_standing: RRSeries
    ) -> None:
        """Each panel contains at least one Ellipse patch."""
        from matplotlib.patches import Ellipse

        fig = plot_poincare_comparison(rr_normal, rr_standing)
        for ax in fig.axes:
            ellipses = [p for p in ax.patches if isinstance(p, Ellipse)]
            assert len(ellipses) >= 1


# ── plot_sd1_sd2_evolution ────────────────────────────────────────────────────


class TestPlotSd1Sd2Evolution:
    """Tests for plot_sd1_sd2_evolution."""

    def test_returns_figure(self, features_single: list[HRVFeatures]) -> None:
        """Single session: function returns a Figure."""
        fig = plot_sd1_sd2_evolution(features_single)
        assert isinstance(fig, Figure)

    def test_multiple_sessions(self, features_multi: list[HRVFeatures]) -> None:
        """Three sessions: function returns a Figure without raising."""
        fig = plot_sd1_sd2_evolution(features_multi)
        assert isinstance(fig, Figure)

    def test_custom_title(self, features_single: list[HRVFeatures]) -> None:
        """Custom title: function returns a Figure without raising."""
        fig = plot_sd1_sd2_evolution(features_single, title="SD Evolution")
        assert isinstance(fig, Figure)

    def test_custom_labels(self, features_multi: list[HRVFeatures]) -> None:
        """Custom labels: function returns a Figure without raising."""
        labels = ["D1", "D2", "D3"]
        fig = plot_sd1_sd2_evolution(features_multi, labels=labels)
        assert isinstance(fig, Figure)

    def test_custom_figsize(self, features_single: list[HRVFeatures]) -> None:
        """Custom figsize: figure dimensions match the requested size."""
        fig = plot_sd1_sd2_evolution(features_single, figsize=(10, 4))
        assert fig.get_size_inches().tolist() == pytest.approx([10.0, 4.0])

    def test_two_axes(self, features_multi: list[HRVFeatures]) -> None:
        """Figure contains two axes (left SD1/SD2, right ratio)."""
        fig = plot_sd1_sd2_evolution(features_multi)
        assert len(fig.axes) == 2

    def test_nan_ratio_accepted(
        self, features_nan_ratio: list[HRVFeatures]
    ) -> None:
        """NaN sd_ratio is plotted as a gap without raising."""
        fig = plot_sd1_sd2_evolution(features_nan_ratio)
        assert isinstance(fig, Figure)

    def test_features_list_not_list_raises(self) -> None:
        """Non-list features_list raises TypeError."""
        with pytest.raises(TypeError, match="features_list must be a list"):
            plot_sd1_sd2_evolution("not_a_list")  # type: ignore[arg-type]

    def test_features_list_empty_raises(self) -> None:
        """Empty features_list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_sd1_sd2_evolution([])

    def test_features_list_wrong_element_raises(self) -> None:
        """Non-HRVFeatures element raises TypeError."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_sd1_sd2_evolution([42])  # type: ignore[list-item]

    def test_labels_length_mismatch_raises(
        self, features_multi: list[HRVFeatures]
    ) -> None:
        """Labels list with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_sd1_sd2_evolution(features_multi, labels=["only one"])

    def test_default_labels_from_date(
        self, features_multi: list[HRVFeatures]
    ) -> None:
        """X-axis labels default to the date attribute of each HRVFeatures."""
        fig = plot_sd1_sd2_evolution(features_multi)
        ax = fig.axes[0]
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        assert "2026-05-18" in tick_labels

    def test_fallback_label_no_date(self) -> None:
        """X-axis falls back to 'Session N' when HRVFeatures.date is None."""
        f = _make_features(date=None)
        fig = plot_sd1_sd2_evolution([f])
        ax = fig.axes[0]
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        assert "Session 1" in tick_labels

    def test_sd1_values_finite(self, features_multi: list[HRVFeatures]) -> None:
        """All SD1 values in the fixture are finite (no NaN or Inf)."""
        for f in features_multi:
            assert math.isfinite(f.sd1)

    def test_sd2_values_positive(self, features_multi: list[HRVFeatures]) -> None:
        """All SD2 values in the fixture are strictly positive."""
        for f in features_multi:
            assert f.sd2 > 0.0
