"""Tests for cardiolab.visualization.hrr_plots."""

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import Wedge

matplotlib.use("Agg")

from cardiolab.protocols.hrr import HRRResult
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.hrr_plots import (
    _angle_from_hrr,
    plot_hrr_comparison,
    plot_hrr_curve,
    plot_hrr_gauge,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

_RNG = np.random.default_rng(42)


def _make_hrr_rr(n: int = 200, seed: int = 42) -> RRSeries:
    """Return a post-exercise RRSeries that recovers from ~500 ms to ~900 ms."""
    rng = np.random.default_rng(seed)
    interp_factor = np.linspace(0, 1, n)
    base_rr = 500.0 + 400.0 * interp_factor
    noise = rng.normal(0, 8, n)
    intervals = np.clip(base_rr + noise, 400.0, 1000.0)
    return RRSeries(intervals=intervals)


def _make_result(
    hrr_60: float = 24.0,
    category: str = "good",
    duration: float = 130.0,
    with_hrr2: bool = True,
    date: str | None = "2024-01-15",
) -> HRRResult:
    """Return an HRRResult with configurable HRR1 and optional HRR2."""
    hr_peak = 120.0
    return HRRResult(
        date=date,
        hr_peak=hr_peak,
        hr_at_60s=hr_peak - hrr_60,
        hr_at_120s=hr_peak - 40.0 if with_hrr2 else float("nan"),
        hrr_60=hrr_60,
        hrr_120=40.0 if with_hrr2 else float("nan"),
        hrr_60_category=category,
        hrr_120_category="excellent" if with_hrr2 else "",
        duration=duration,
    )


@pytest.fixture()
def rr_hrr() -> RRSeries:
    """Return a standard 200-interval post-exercise RRSeries."""
    return _make_hrr_rr()


@pytest.fixture()
def rr_short() -> RRSeries:
    """Return a short RRSeries (only 70 s, no HRR2 window)."""
    return _make_hrr_rr(n=80, seed=7)


@pytest.fixture()
def result_good() -> HRRResult:
    """Return an HRRResult with HRR1=24 (good) and HRR2 available."""
    return _make_result(hrr_60=24.0, category="good", duration=130.0)


@pytest.fixture()
def result_excellent() -> HRRResult:
    """Return an HRRResult with HRR1=30 (excellent) and HRR2 available."""
    return _make_result(hrr_60=30.0, category="excellent", duration=130.0)


@pytest.fixture()
def result_impaired() -> HRRResult:
    """Return an HRRResult with HRR1=8 (impaired), no HRR2."""
    return _make_result(
        hrr_60=8.0, category="impaired", duration=70.0, with_hrr2=False
    )


@pytest.fixture()
def result_no_date() -> HRRResult:
    """Return an HRRResult with no date set."""
    return _make_result(date=None)


# ── _angle_from_hrr ───────────────────────────────────────────────────────────


class TestAngleFromHrr:
    """Unit tests for the _angle_from_hrr helper."""

    def test_zero_maps_to_180(self) -> None:
        """Return 180.0 for 0 bpm (left end of gauge)."""
        assert _angle_from_hrr(0.0) == pytest.approx(180.0)

    def test_max_maps_to_zero(self) -> None:
        """Return 0.0 for 40 bpm (right end of gauge)."""
        assert _angle_from_hrr(40.0) == pytest.approx(0.0)

    def test_midpoint(self) -> None:
        """Return 90.0 for 20 bpm (midpoint of gauge)."""
        assert _angle_from_hrr(20.0) == pytest.approx(90.0)

    def test_clamp_below_zero(self) -> None:
        """Clamp values below 0 to 180°."""
        assert _angle_from_hrr(-5.0) == pytest.approx(180.0)

    def test_clamp_above_max(self) -> None:
        """Clamp values above max to 0°."""
        assert _angle_from_hrr(999.0) == pytest.approx(0.0)


# ── plot_hrr_curve ────────────────────────────────────────────────────────────


class TestPlotHrrCurve:
    """Tests for plot_hrr_curve."""

    def test_returns_figure(self, rr_hrr: RRSeries, result_good: HRRResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_hrr_curve(rr_hrr, result_good)
        assert isinstance(fig, Figure)

    def test_single_axis(self, rr_hrr: RRSeries, result_good: HRRResult) -> None:
        """Produce exactly one axes."""
        fig = plot_hrr_curve(rr_hrr, result_good)
        assert len(fig.axes) == 1

    def test_custom_title(self, rr_hrr: RRSeries, result_good: HRRResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_hrr_curve(rr_hrr, result_good, title="My HRR")
        assert fig.texts[0].get_text() == "My HRR"

    def test_custom_figsize(self, rr_hrr: RRSeries, result_good: HRRResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_hrr_curve(rr_hrr, result_good, figsize=(8, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(4.0)

    def test_hrr2_present_when_duration_sufficient(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Plot HRR2 marker when result duration >= 120 s."""
        fig = plot_hrr_curve(rr_hrr, result_good)
        ax = fig.axes[0]
        labels = [line.get_label() for line in ax.get_lines()]
        assert any("HRR2" in lbl for lbl in labels) or len(ax.collections) >= 2

    def test_hrr2_absent_when_duration_short(
        self, rr_short: RRSeries, result_impaired: HRRResult
    ) -> None:
        """Skip HRR2 marker when duration < 120 s or hrr_120 is nan."""
        fig = plot_hrr_curve(rr_short, result_impaired)
        ax = fig.axes[0]
        labels = [line.get_label() for line in ax.get_lines()]
        assert not any("HRR2" in lbl for lbl in labels)

    def test_type_error_rr(self, result_good: HRRResult) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_hrr_curve([800, 810, 820, 815, 830], result_good)  # type: ignore[arg-type]

    def test_type_error_result(self, rr_hrr: RRSeries) -> None:
        """Raise TypeError when result is not an HRRResult."""
        with pytest.raises(TypeError, match="HRRResult"):
            plot_hrr_curve(rr_hrr, {"hrr_60": 20})  # type: ignore[arg-type]

    def test_value_error_too_few_intervals(self, result_good: HRRResult) -> None:
        """Raise ValueError when rr has fewer than 5 intervals."""
        tiny = RRSeries(intervals=[800.0, 810.0, 820.0, 815.0])
        with pytest.raises(ValueError, match="at least"):
            plot_hrr_curve(tiny, result_good)

    def test_axis_labels(self, rr_hrr: RRSeries, result_good: HRRResult) -> None:
        """Set x-axis and y-axis labels."""
        fig = plot_hrr_curve(rr_hrr, result_good)
        ax = fig.axes[0]
        assert "Time" in ax.get_xlabel()
        assert "Heart rate" in ax.get_ylabel() or "bpm" in ax.get_ylabel()


# ── plot_hrr_comparison ───────────────────────────────────────────────────────


class TestPlotHrrComparison:
    """Tests for plot_hrr_comparison."""

    def test_returns_figure(
        self, rr_hrr: RRSeries, rr_short: RRSeries,
        result_good: HRRResult, result_impaired: HRRResult,
    ) -> None:
        """Return a matplotlib Figure."""
        fig = plot_hrr_comparison(
            [rr_hrr, rr_short], [result_good, result_impaired]
        )
        assert isinstance(fig, Figure)

    def test_single_axis(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Produce exactly one axes."""
        fig = plot_hrr_comparison([rr_hrr], [result_good])
        assert len(fig.axes) == 1

    def test_custom_title(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Accept and apply a custom title."""
        fig = plot_hrr_comparison([rr_hrr], [result_good], title="My Comparison")
        assert fig.texts[0].get_text() == "My Comparison"

    def test_custom_figsize(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_hrr_comparison([rr_hrr], [result_good], figsize=(10, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(4.0)

    def test_custom_labels(
        self, rr_hrr: RRSeries, rr_short: RRSeries,
        result_good: HRRResult, result_impaired: HRRResult,
    ) -> None:
        """Accept custom session labels in legend."""
        labels = ["Week 1", "Week 2"]
        fig = plot_hrr_comparison(
            [rr_hrr, rr_short],
            [result_good, result_impaired],
            labels=labels,
        )
        legend_texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert any("Week 1" in t for t in legend_texts)
        assert any("Week 2" in t for t in legend_texts)

    def test_default_labels_use_date(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Fall back to result.date when no labels provided."""
        fig = plot_hrr_comparison([rr_hrr], [result_good])
        legend_texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert any("2024-01-15" in t for t in legend_texts)

    def test_default_labels_session_n_when_no_date(
        self, rr_hrr: RRSeries, result_no_date: HRRResult
    ) -> None:
        """Fall back to 'Session N' when result.date is None."""
        fig = plot_hrr_comparison([rr_hrr], [result_no_date])
        legend_texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert any("Session" in t for t in legend_texts)

    def test_type_error_rr_list(self, result_good: HRRResult) -> None:
        """Raise TypeError when rr_list is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_hrr_comparison("not_a_list", [result_good])  # type: ignore[arg-type]

    def test_type_error_results(self, rr_hrr: RRSeries) -> None:
        """Raise TypeError when results is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_hrr_comparison([rr_hrr], "not_a_list")  # type: ignore[arg-type]

    def test_value_error_empty_list(self, result_good: HRRResult) -> None:
        """Raise ValueError when rr_list is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_hrr_comparison([], [])

    def test_value_error_length_mismatch(
        self, rr_hrr: RRSeries, result_good: HRRResult, result_impaired: HRRResult
    ) -> None:
        """Raise ValueError when rr_list and results lengths differ."""
        with pytest.raises(ValueError, match="length"):
            plot_hrr_comparison([rr_hrr], [result_good, result_impaired])

    def test_value_error_labels_mismatch(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Raise ValueError when labels length mismatches results."""
        with pytest.raises(ValueError, match="labels length"):
            plot_hrr_comparison([rr_hrr], [result_good], labels=["A", "B"])

    def test_type_error_rr_element(self, result_good: HRRResult) -> None:
        """Raise TypeError when an rr_list element is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_hrr_comparison(["not_a_series"], [result_good])  # type: ignore[list-item]

    def test_type_error_result_element(self, rr_hrr: RRSeries) -> None:
        """Raise TypeError when a results element is not an HRRResult."""
        with pytest.raises(TypeError, match="HRRResult"):
            plot_hrr_comparison([rr_hrr], [{"hrr_60": 20}])  # type: ignore[list-item]

    def test_ylim_starts_at_zero(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Set y-axis lower limit to 0 (HR drop cannot be negative)."""
        fig = plot_hrr_comparison([rr_hrr], [result_good])
        assert fig.axes[0].get_ylim()[0] >= 0.0

    def test_xlim_starts_at_zero(
        self, rr_hrr: RRSeries, result_good: HRRResult
    ) -> None:
        """Set x-axis lower limit to 0."""
        fig = plot_hrr_comparison([rr_hrr], [result_good])
        assert fig.axes[0].get_xlim()[0] >= 0.0


# ── plot_hrr_gauge ────────────────────────────────────────────────────────────


class TestPlotHrrGauge:
    """Tests for plot_hrr_gauge."""

    def test_returns_figure(self, result_good: HRRResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_hrr_gauge(result_good)
        assert isinstance(fig, Figure)

    def test_single_axis(self, result_good: HRRResult) -> None:
        """Produce exactly one axes."""
        fig = plot_hrr_gauge(result_good)
        assert len(fig.axes) == 1

    def test_custom_title(self, result_good: HRRResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_hrr_gauge(result_good, title="My Gauge")
        assert fig.texts[0].get_text() == "My Gauge"

    def test_custom_figsize(self, result_good: HRRResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_hrr_gauge(result_good, figsize=(8, 6))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(6.0)

    def test_four_wedge_sectors(self, result_good: HRRResult) -> None:
        """Draw exactly 4 coloured annular Wedge sectors plus 1 outline Wedge."""
        fig = plot_hrr_gauge(result_good)
        ax = fig.axes[0]
        wedges = [p for p in ax.patches if isinstance(p, Wedge)]
        assert len(wedges) >= 4

    def test_axis_off(self, result_good: HRRResult) -> None:
        """Turn off the axis frame for a clean gauge display."""
        fig = plot_hrr_gauge(result_good)
        ax = fig.axes[0]
        assert not ax.axison

    def test_aspect_equal(self, result_good: HRRResult) -> None:
        """Set equal aspect ratio so the gauge is circular."""
        fig = plot_hrr_gauge(result_good)
        ax = fig.axes[0]
        assert ax.get_aspect() in ("equal", pytest.approx(1.0))

    def test_type_error_result(self) -> None:
        """Raise TypeError when result is not an HRRResult."""
        with pytest.raises(TypeError, match="HRRResult"):
            plot_hrr_gauge({"hrr_60": 20})  # type: ignore[arg-type]

    def test_impaired_category_text(self, result_impaired: HRRResult) -> None:
        """Display 'Impaired' text in the gauge for an impaired result."""
        fig = plot_hrr_gauge(result_impaired)
        ax = fig.axes[0]
        texts = [t.get_text().lower() for t in ax.texts]
        assert any("impaired" in t for t in texts)

    def test_excellent_category_text(self, result_excellent: HRRResult) -> None:
        """Display 'Excellent' text in the gauge for an excellent result."""
        fig = plot_hrr_gauge(result_excellent)
        ax = fig.axes[0]
        texts = [t.get_text().lower() for t in ax.texts]
        assert any("excellent" in t for t in texts)

    def test_hrr1_value_displayed(self, result_good: HRRResult) -> None:
        """Display the numeric HRR1 value in the gauge."""
        fig = plot_hrr_gauge(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("24" in t for t in texts)
