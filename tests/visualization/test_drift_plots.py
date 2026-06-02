"""Tests for cardiolab.visualization.drift_plots."""

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import Patch

matplotlib.use("Agg")

from cardiolab.protocols.cardiac_drift import DriftResult, cardiac_drift
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.drift_plots import (
    plot_drift_curve,
    plot_drift_zones,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_drift_rr(
    n: int = 500,
    hr_start: float = 80.0,
    hr_end: float = 86.0,
    seed: int = 42,
) -> RRSeries:
    """Return a constant-load RRSeries with a mild upward HR drift."""
    rng = np.random.default_rng(seed)
    factor = np.linspace(0, 1, n)
    rr_start = 60_000.0 / hr_start
    rr_end = 60_000.0 / hr_end
    base_rr = rr_start + (rr_end - rr_start) * factor
    noise = rng.normal(0, 10, n)
    return RRSeries(np.clip(base_rr + noise, 400.0, 1000.0))


def _make_result(
    drift_rate: float = 0.9,
    interpretation: str = "mild",
    date: str | None = "2024-06-01",
) -> DriftResult:
    """Return a DriftResult with configurable drift rate and category."""
    return DriftResult(
        date=date,
        drift_rate=drift_rate,
        drift_magnitude=drift_rate * 5.0,
        r_squared=0.85,
        drift_detected=abs(drift_rate) >= 0.5,
        initial_hr=80.0,
        final_hr=80.0 + drift_rate * 5.0,
        n_windows=6,
        interpretation=interpretation,
        duration=360.0,
    )


@pytest.fixture()
def rr_drift() -> RRSeries:
    """Return a 500-interval exercise RRSeries with mild upward HR drift."""
    return _make_drift_rr()


@pytest.fixture()
def rr_strong() -> RRSeries:
    """Return a 700-interval RRSeries with a strong upward HR drift."""
    return _make_drift_rr(n=700, hr_start=75.0, hr_end=100.0, seed=7)


@pytest.fixture()
def result_mild() -> DriftResult:
    """Return a mild DriftResult."""
    return _make_result(drift_rate=0.9, interpretation="mild")


@pytest.fixture()
def result_no_drift() -> DriftResult:
    """Return a no-drift DriftResult."""
    return _make_result(drift_rate=0.2, interpretation="no_drift", date="2024-06-02")


@pytest.fixture()
def result_moderate() -> DriftResult:
    """Return a moderate DriftResult."""
    return _make_result(drift_rate=2.1, interpretation="moderate", date="2024-06-03")


@pytest.fixture()
def result_strong() -> DriftResult:
    """Return a strong DriftResult."""
    return _make_result(drift_rate=3.5, interpretation="strong", date="2024-06-04")


@pytest.fixture()
def result_no_date() -> DriftResult:
    """Return a DriftResult with no date."""
    return _make_result(date=None)


# ── plot_drift_curve ──────────────────────────────────────────────────────────


class TestPlotDriftCurve:
    """Tests for plot_drift_curve."""

    def test_returns_figure(self, rr_drift: RRSeries, result_mild: DriftResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_drift_curve(rr_drift, result_mild)
        assert isinstance(fig, Figure)

    def test_single_axis(self, rr_drift: RRSeries, result_mild: DriftResult) -> None:
        """Produce exactly one axes."""
        fig = plot_drift_curve(rr_drift, result_mild)
        assert len(fig.axes) == 1

    def test_custom_title(self, rr_drift: RRSeries, result_mild: DriftResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_drift_curve(rr_drift, result_mild, title="My Drift")
        assert fig.texts[0].get_text() == "My Drift"

    def test_custom_figsize(self, rr_drift: RRSeries, result_mild: DriftResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_drift_curve(rr_drift, result_mild, figsize=(8, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(4.0)

    def test_scatter_points_present(
        self, rr_drift: RRSeries, result_mild: DriftResult
    ) -> None:
        """Draw at least one scatter collection (window HR points)."""
        fig = plot_drift_curve(rr_drift, result_mild)
        ax = fig.axes[0]
        assert len(ax.collections) >= 1

    def test_regression_line_present(
        self, rr_drift: RRSeries, result_mild: DriftResult
    ) -> None:
        """Draw at least one Line2D (regression line)."""
        fig = plot_drift_curve(rr_drift, result_mild)
        ax = fig.axes[0]
        assert len(ax.lines) >= 1

    def test_axis_labels(self, rr_drift: RRSeries, result_mild: DriftResult) -> None:
        """Set time x-axis and HR y-axis labels."""
        fig = plot_drift_curve(rr_drift, result_mild)
        ax = fig.axes[0]
        assert "min" in ax.get_xlabel().lower() or "time" in ax.get_xlabel().lower()
        assert "bpm" in ax.get_ylabel().lower() or "heart" in ax.get_ylabel().lower()

    def test_annotation_box_contains_drift_rate(
        self, rr_drift: RRSeries, result_mild: DriftResult
    ) -> None:
        """Annotation box text contains the drift rate value."""
        fig = plot_drift_curve(rr_drift, result_mild)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("0.90" in t or "Drift" in t for t in texts)

    def test_no_drift_background_green(
        self, rr_drift: RRSeries, result_no_drift: DriftResult
    ) -> None:
        """Apply a greenish background for no-drift category."""
        fig = plot_drift_curve(rr_drift, result_no_drift)
        ax = fig.axes[0]
        fc = ax.get_facecolor()
        # Green channel should dominate for no_drift (#eafaf1)
        assert fc[1] > fc[0]

    def test_strong_drift_background_red(
        self, rr_strong: RRSeries, result_strong: DriftResult
    ) -> None:
        """Apply a reddish background for strong drift category."""
        fig = plot_drift_curve(rr_strong, result_strong)
        ax = fig.axes[0]
        fc = ax.get_facecolor()
        # Red channel should dominate for strong (#fdf0ef)
        assert fc[0] > fc[2]

    def test_type_error_rr(self, result_mild: DriftResult) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_drift_curve([800] * 500, result_mild)  # type: ignore[arg-type]

    def test_type_error_result(self, rr_drift: RRSeries) -> None:
        """Raise TypeError when result is not a DriftResult."""
        with pytest.raises(TypeError, match="DriftResult"):
            plot_drift_curve(rr_drift, {"drift_rate": 1.0})  # type: ignore[arg-type]

    def test_value_error_too_short(self, result_mild: DriftResult) -> None:
        """Raise ValueError when RRSeries is too short for 3 windows."""
        short_rr = _make_drift_rr(n=60)  # ~43 s — fewer than 3×60 s windows
        with pytest.raises(ValueError, match="too short"):
            plot_drift_curve(short_rr, result_mild)

    def test_computed_result_roundtrip(self, rr_drift: RRSeries) -> None:
        """Accept a DriftResult computed directly from the same RRSeries."""
        result = cardiac_drift(rr_drift)
        fig = plot_drift_curve(rr_drift, result)
        assert isinstance(fig, Figure)


# ── plot_drift_zones ──────────────────────────────────────────────────────────


class TestPlotDriftZones:
    """Tests for plot_drift_zones."""

    def test_returns_figure(
        self,
        result_mild: DriftResult,
        result_no_drift: DriftResult,
        result_moderate: DriftResult,
    ) -> None:
        """Return a matplotlib Figure."""
        fig = plot_drift_zones([result_mild, result_no_drift, result_moderate])
        assert isinstance(fig, Figure)

    def test_single_axis(self, result_mild: DriftResult) -> None:
        """Produce exactly one axes."""
        fig = plot_drift_zones([result_mild])
        assert len(fig.axes) == 1

    def test_custom_title(self, result_mild: DriftResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_drift_zones([result_mild], title="My Drift Evolution")
        assert fig.texts[0].get_text() == "My Drift Evolution"

    def test_custom_figsize(self, result_mild: DriftResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_drift_zones([result_mild], figsize=(10, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(4.0)

    def test_four_zone_patches(self, result_mild: DriftResult) -> None:
        """Draw at least four background Patch regions (one per zone)."""
        fig = plot_drift_zones([result_mild])
        ax = fig.axes[0]
        patches = [p for p in ax.patches if isinstance(p, Patch)]
        assert len(patches) >= 4

    def test_legend_has_four_entries(self, result_mild: DriftResult) -> None:
        """Legend contains exactly four zone entries."""
        fig = plot_drift_zones([result_mild])
        legend = fig.axes[0].get_legend()
        assert len(legend.get_texts()) == 4

    def test_custom_labels_in_xticklabels(
        self, result_mild: DriftResult, result_no_drift: DriftResult
    ) -> None:
        """Display custom labels on x-axis ticks."""
        labels = ["Session A", "Session B"]
        fig = plot_drift_zones([result_mild, result_no_drift], session_labels=labels)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "Session A" in tick_texts
        assert "Session B" in tick_texts

    def test_default_labels_use_date(self, result_mild: DriftResult) -> None:
        """Fall back to result.date when no labels provided."""
        fig = plot_drift_zones([result_mild])
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert any("2024-06-01" in t for t in tick_texts)

    def test_default_labels_session_n_when_no_date(
        self, result_no_date: DriftResult
    ) -> None:
        """Fall back to 'Session N' when result.date is None."""
        fig = plot_drift_zones([result_no_date])
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert any("Session" in t for t in tick_texts)

    def test_ylim_starts_at_zero(self, result_mild: DriftResult) -> None:
        """Set y-axis lower limit to 0."""
        fig = plot_drift_zones([result_mild])
        assert fig.axes[0].get_ylim()[0] == pytest.approx(0.0)

    def test_strong_drift_extends_ymax(self, result_strong: DriftResult) -> None:
        """Extend y-axis above default max when drift exceeds 5 bpm/min."""
        strong = _make_result(drift_rate=6.0, interpretation="strong")
        fig = plot_drift_zones([strong])
        assert fig.axes[0].get_ylim()[1] > 5.0

    def test_type_error_not_list(self, result_mild: DriftResult) -> None:
        """Raise TypeError when results is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_drift_zones(result_mild)  # type: ignore[arg-type]

    def test_value_error_empty_list(self) -> None:
        """Raise ValueError when results is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_drift_zones([])

    def test_type_error_wrong_element(self) -> None:
        """Raise TypeError when a results element is not a DriftResult."""
        with pytest.raises(TypeError, match="DriftResult"):
            plot_drift_zones([{"drift_rate": 1.0}])  # type: ignore[list-item]

    def test_value_error_labels_mismatch(self, result_mild: DriftResult) -> None:
        """Raise ValueError when labels length mismatches results."""
        with pytest.raises(ValueError, match="labels length"):
            plot_drift_zones([result_mild], session_labels=["A", "B"])

    def test_all_four_categories(
        self,
        result_no_drift: DriftResult,
        result_mild: DriftResult,
        result_moderate: DriftResult,
        result_strong: DriftResult,
    ) -> None:
        """Accept all four clinical categories without error."""
        fig = plot_drift_zones(
            [result_no_drift, result_mild, result_moderate, result_strong]
        )
        assert isinstance(fig, Figure)
