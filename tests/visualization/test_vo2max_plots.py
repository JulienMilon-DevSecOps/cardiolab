"""Tests for cardiolab.visualization.vo2max_plots."""

import math

import matplotlib
import pytest
from matplotlib.figure import Figure
from matplotlib.patches import Wedge

matplotlib.use("Agg")

from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.visualization.vo2max_plots import (
    plot_vo2max_comparison,
    plot_vo2max_evolution,
    plot_vo2max_gauge,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_result(
    fitness_category: str = "good",
    with_uth: bool = True,
    date: str | None = "2024-06-01",
) -> VO2maxResult:
    """Return a VO2maxResult with configurable category and Uth availability."""
    vo2max_uth = 45.0 if with_uth else float("nan")
    hr_max = 185.0 if with_uth else float("nan")
    return VO2maxResult(
        date=date,
        vo2max_uth=vo2max_uth,
        vo2max_esco_flatt=43.0,
        vo2max_ln_rmssd=44.5,
        hr_rest=58.0,
        hr_max=hr_max,
        rmssd_used=42.0,
        ln_rmssd_used=math.log(42.0),
        fitness_category=fitness_category,
    )


@pytest.fixture()
def result_good() -> VO2maxResult:
    """Return a good-category VO2maxResult with Uth available."""
    return _make_result(fitness_category="good", with_uth=True)


@pytest.fixture()
def result_excellent() -> VO2maxResult:
    """Return an excellent-category VO2maxResult."""
    return VO2maxResult(
        date="2024-06-02",
        vo2max_uth=62.0,
        vo2max_esco_flatt=60.5,
        vo2max_ln_rmssd=61.0,
        hr_rest=48.0,
        hr_max=195.0,
        rmssd_used=65.0,
        ln_rmssd_used=math.log(65.0),
        fitness_category="excellent",
    )


@pytest.fixture()
def result_poor() -> VO2maxResult:
    """Return a poor-category VO2maxResult without Uth."""
    return VO2maxResult(
        date="2024-06-03",
        vo2max_uth=float("nan"),
        vo2max_esco_flatt=24.0,
        vo2max_ln_rmssd=22.5,
        hr_rest=82.0,
        hr_max=float("nan"),
        rmssd_used=18.0,
        ln_rmssd_used=math.log(18.0),
        fitness_category="poor",
    )


@pytest.fixture()
def result_no_uth() -> VO2maxResult:
    """Return a VO2maxResult where Uth is NaN (no hr_max provided)."""
    return _make_result(fitness_category="fair", with_uth=False, date="2024-06-04")


@pytest.fixture()
def result_no_date() -> VO2maxResult:
    """Return a VO2maxResult with no date."""
    return _make_result(date=None)


# ── plot_vo2max_comparison ────────────────────────────────────────────────────


class TestPlotVo2maxComparison:
    """Tests for plot_vo2max_comparison."""

    def test_returns_figure(self, result_good: VO2maxResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_vo2max_comparison(result_good)
        assert isinstance(fig, Figure)

    def test_single_axis(self, result_good: VO2maxResult) -> None:
        """Produce exactly one axes."""
        fig = plot_vo2max_comparison(result_good)
        assert len(fig.axes) == 1

    def test_custom_title(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_vo2max_comparison(result_good, title="My VO2max")
        assert fig.texts[0].get_text() == "My VO2max"

    def test_custom_figsize(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_vo2max_comparison(result_good, figsize=(8, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(4.0)

    def test_three_bars_with_uth(self, result_good: VO2maxResult) -> None:
        """Draw three bars when Uth is available."""
        fig = plot_vo2max_comparison(result_good)
        ax = fig.axes[0]
        bars = ax.patches
        assert len(bars) >= 3

    def test_two_bars_without_uth(self, result_no_uth: VO2maxResult) -> None:
        """Draw two bars when Uth is NaN."""
        fig = plot_vo2max_comparison(result_no_uth)
        ax = fig.axes[0]
        # Only Esco-Flatt and ln-RMSSD bars
        assert len(ax.patches) >= 2

    def test_bar_count_with_uth(self, result_good: VO2maxResult) -> None:
        """Exactly 3 bars rendered when Uth available."""
        fig = plot_vo2max_comparison(result_good)
        ax = fig.axes[0]
        bar_count = len(
            [p for p in ax.patches if hasattr(p, "get_width") and p.get_width() > 0]
        )
        assert bar_count >= 2

    def test_xticklabels_with_uth(self, result_good: VO2maxResult) -> None:
        """X-tick labels include Uth, Esco-Flatt, ln-RMSSD when Uth present."""
        fig = plot_vo2max_comparison(result_good)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert any("Uth" in t for t in tick_texts)
        assert any("Esco" in t or "RMSSD" in t for t in tick_texts)

    def test_xticklabels_without_uth(self, result_no_uth: VO2maxResult) -> None:
        """X-tick labels do not include Uth when Uth is NaN."""
        fig = plot_vo2max_comparison(result_no_uth)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert not any("Uth" in t for t in tick_texts)

    def test_annotation_box_contains_category(self, result_good: VO2maxResult) -> None:
        """Annotation box text contains the fitness category."""
        fig = plot_vo2max_comparison(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("Good" in t or "Category" in t for t in texts)

    def test_annotation_box_contains_rmssd(self, result_good: VO2maxResult) -> None:
        """Annotation box text contains the RMSSD value."""
        fig = plot_vo2max_comparison(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("42.0" in t for t in texts)

    def test_annotation_hr_max_na_when_no_uth(
        self, result_no_uth: VO2maxResult
    ) -> None:
        """Annotation shows 'n/a' for HR max when not provided."""
        fig = plot_vo2max_comparison(result_no_uth)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("n/a" in t for t in texts)

    def test_ylim_starts_at_zero(self, result_good: VO2maxResult) -> None:
        """Y-axis lower limit is 0."""
        fig = plot_vo2max_comparison(result_good)
        assert fig.axes[0].get_ylim()[0] == pytest.approx(0.0)

    def test_ylabel_contains_vo2max(self, result_good: VO2maxResult) -> None:
        """Y-axis label mentions VO2max."""
        fig = plot_vo2max_comparison(result_good)
        assert "VO2max" in fig.axes[0].get_ylabel() or "mL" in fig.axes[0].get_ylabel()

    def test_type_error_result(self) -> None:
        """Raise TypeError when result is not a VO2maxResult."""
        with pytest.raises(TypeError, match="VO2maxResult"):
            plot_vo2max_comparison({"fitness_category": "good"})  # type: ignore[arg-type]

    def test_excellent_result(self, result_excellent: VO2maxResult) -> None:
        """Accept an excellent-category result without error."""
        fig = plot_vo2max_comparison(result_excellent)
        assert isinstance(fig, Figure)

    def test_poor_result_no_uth(self, result_poor: VO2maxResult) -> None:
        """Accept a poor-category result without Uth."""
        fig = plot_vo2max_comparison(result_poor)
        assert isinstance(fig, Figure)


# ── plot_vo2max_evolution ─────────────────────────────────────────────────────


class TestPlotVo2maxEvolution:
    """Tests for plot_vo2max_evolution."""

    def test_returns_figure(self, result_good: VO2maxResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_vo2max_evolution([result_good])
        assert isinstance(fig, Figure)

    def test_single_axis(self, result_good: VO2maxResult) -> None:
        """Produce exactly one axes."""
        fig = plot_vo2max_evolution([result_good])
        assert len(fig.axes) == 1

    def test_custom_title(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_vo2max_evolution([result_good], title="My Evolution")
        assert fig.texts[0].get_text() == "My Evolution"

    def test_custom_figsize(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_vo2max_evolution([result_good], figsize=(10, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(4.0)

    def test_uncertainty_band_present(self, result_good: VO2maxResult) -> None:
        """Draw a ±10 % fill_between band (PolyCollection)."""
        from matplotlib.collections import PolyCollection

        fig = plot_vo2max_evolution([result_good])
        ax = fig.axes[0]
        poly = [c for c in ax.collections if isinstance(c, PolyCollection)]
        assert len(poly) >= 1

    def test_best_estimate_line_present(self, result_good: VO2maxResult) -> None:
        """Draw at least one Line2D (best-estimate line)."""
        fig = plot_vo2max_evolution([result_good])
        ax = fig.axes[0]
        assert len(ax.lines) >= 1

    def test_scatter_dots_present(
        self,
        result_good: VO2maxResult,
        result_excellent: VO2maxResult,
    ) -> None:
        """Draw scatter dots (PathCollection) for each session."""
        from matplotlib.collections import PathCollection

        fig = plot_vo2max_evolution([result_good, result_excellent])
        ax = fig.axes[0]
        dots = [c for c in ax.collections if isinstance(c, PathCollection)]
        assert len(dots) >= 1

    def test_custom_labels_in_xticklabels(
        self,
        result_good: VO2maxResult,
        result_excellent: VO2maxResult,
    ) -> None:
        """Display custom labels on x-axis ticks."""
        labels = ["Session A", "Session B"]
        fig = plot_vo2max_evolution([result_good, result_excellent], labels=labels)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "Session A" in tick_texts
        assert "Session B" in tick_texts

    def test_default_labels_use_date(self, result_good: VO2maxResult) -> None:
        """Fall back to result.date when no labels provided."""
        fig = plot_vo2max_evolution([result_good])
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert any("2024-06-01" in t for t in tick_texts)

    def test_default_labels_session_n_when_no_date(
        self, result_no_date: VO2maxResult
    ) -> None:
        """Fall back to 'Session N' when result.date is None."""
        fig = plot_vo2max_evolution([result_no_date])
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert any("Session" in t for t in tick_texts)

    def test_ylim_starts_at_zero(self, result_good: VO2maxResult) -> None:
        """Y-axis lower limit is 0."""
        fig = plot_vo2max_evolution([result_good])
        assert fig.axes[0].get_ylim()[0] == pytest.approx(0.0)

    def test_ymax_extends_for_high_vo2max(self, result_excellent: VO2maxResult) -> None:
        """Y-axis upper limit accommodates values above default 70."""
        high = VO2maxResult(
            date="2024-06-05",
            vo2max_uth=75.0,
            vo2max_esco_flatt=73.0,
            vo2max_ln_rmssd=74.0,
            hr_rest=42.0,
            hr_max=200.0,
            rmssd_used=80.0,
            ln_rmssd_used=math.log(80.0),
            fitness_category="excellent",
        )
        fig = plot_vo2max_evolution([high])
        assert fig.axes[0].get_ylim()[1] > 70.0

    def test_legend_present(self, result_good: VO2maxResult) -> None:
        """Legend is drawn with at least one entry."""
        fig = plot_vo2max_evolution([result_good])
        legend = fig.axes[0].get_legend()
        assert legend is not None

    def test_type_error_not_list(self, result_good: VO2maxResult) -> None:
        """Raise TypeError when results is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_vo2max_evolution(result_good)  # type: ignore[arg-type]

    def test_value_error_empty_list(self) -> None:
        """Raise ValueError when results is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_vo2max_evolution([])

    def test_type_error_wrong_element(self) -> None:
        """Raise TypeError when a results element is not a VO2maxResult."""
        with pytest.raises(TypeError, match="VO2maxResult"):
            plot_vo2max_evolution([{"fitness_category": "good"}])  # type: ignore[list-item]

    def test_value_error_labels_mismatch(self, result_good: VO2maxResult) -> None:
        """Raise ValueError when labels length mismatches results."""
        with pytest.raises(ValueError, match="labels length"):
            plot_vo2max_evolution([result_good], labels=["A", "B"])

    def test_multi_session_mix(
        self,
        result_good: VO2maxResult,
        result_excellent: VO2maxResult,
        result_poor: VO2maxResult,
    ) -> None:
        """Accept mixed categories without error."""
        fig = plot_vo2max_evolution([result_poor, result_good, result_excellent])
        assert isinstance(fig, Figure)

    def test_uth_used_as_best_when_available(self, result_good: VO2maxResult) -> None:
        """Best estimate is Uth (45.0) not ln-RMSSD (44.5) when Uth is present."""
        fig = plot_vo2max_evolution([result_good])
        ax = fig.axes[0]
        best_line = next(
            line for line in ax.lines if line.get_label() == "Best estimate"
        )
        assert best_line.get_ydata()[0] == pytest.approx(45.0)

    def test_ln_rmssd_used_when_no_uth(self, result_no_uth: VO2maxResult) -> None:
        """Best estimate falls back to ln-RMSSD when Uth is NaN."""
        fig = plot_vo2max_evolution([result_no_uth])
        ax = fig.axes[0]
        best_line = next(
            line for line in ax.lines if line.get_label() == "Best estimate"
        )
        assert best_line.get_ydata()[0] == pytest.approx(result_no_uth.vo2max_ln_rmssd)


# ── plot_vo2max_gauge ─────────────────────────────────────────────────────────


class TestPlotVo2maxGauge:
    """Tests for plot_vo2max_gauge."""

    def test_returns_figure(self, result_good: VO2maxResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_vo2max_gauge(result_good)
        assert isinstance(fig, Figure)

    def test_single_axis(self, result_good: VO2maxResult) -> None:
        """Produce exactly one axes."""
        fig = plot_vo2max_gauge(result_good)
        assert len(fig.axes) == 1

    def test_custom_title(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom title."""
        fig = plot_vo2max_gauge(result_good, title="My Gauge")
        assert fig.texts[0].get_text() == "My Gauge"

    def test_custom_figsize(self, result_good: VO2maxResult) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_vo2max_gauge(result_good, figsize=(8, 5))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(5.0)

    def test_five_wedge_sectors(self, result_good: VO2maxResult) -> None:
        """Draw five Wedge patches for the five ACSM fitness zones."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        wedges = [p for p in ax.patches if isinstance(p, Wedge)]
        assert len(wedges) >= 5

    def test_needle_line_present(self, result_good: VO2maxResult) -> None:
        """Draw at least one Line2D (needle)."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        assert len(ax.lines) >= 1

    def test_central_value_text_present(self, result_good: VO2maxResult) -> None:
        """Show the numeric best-estimate value in the central text."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("45" in t for t in texts)

    def test_central_unit_text_present(self, result_good: VO2maxResult) -> None:
        """Show 'mL/kg/min' unit text below the value."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("mL" in t for t in texts)

    def test_category_text_present(self, result_good: VO2maxResult) -> None:
        """Show the fitness category text below the unit."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        assert any("Good" in t for t in texts)

    def test_excellent_result(self, result_excellent: VO2maxResult) -> None:
        """Accept an excellent-category result without error."""
        fig = plot_vo2max_gauge(result_excellent)
        assert isinstance(fig, Figure)

    def test_poor_result_no_uth(self, result_poor: VO2maxResult) -> None:
        """Accept a poor-category result without Uth."""
        fig = plot_vo2max_gauge(result_poor)
        assert isinstance(fig, Figure)

    def test_gauge_no_uth_uses_ln_rmssd(self, result_no_uth: VO2maxResult) -> None:
        """Central value is ln-RMSSD when Uth not available."""
        fig = plot_vo2max_gauge(result_no_uth)
        ax = fig.axes[0]
        texts = [t.get_text() for t in ax.texts]
        expected = f"{result_no_uth.vo2max_ln_rmssd:.0f}"
        assert any(expected in t for t in texts)

    def test_type_error_result(self) -> None:
        """Raise TypeError when result is not a VO2maxResult."""
        with pytest.raises(TypeError, match="VO2maxResult"):
            plot_vo2max_gauge({"fitness_category": "good"})  # type: ignore[arg-type]

    def test_axis_is_off(self, result_good: VO2maxResult) -> None:
        """Gauge axis has no visible axes frame."""
        fig = plot_vo2max_gauge(result_good)
        ax = fig.axes[0]
        assert not ax.axison
