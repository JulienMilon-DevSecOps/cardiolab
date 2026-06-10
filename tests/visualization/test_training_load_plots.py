"""Unit tests for cardiolab.visualization.training_load_plots."""

from __future__ import annotations

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.analytics.training_load import (  # noqa: E402
    TrainingLoad,
    compute_atl,
    compute_ctl,
    compute_tsb,
)
from cardiolab.visualization.training_load_plots import (  # noqa: E402
    plot_atl_ctl_tsb,
    plot_trimp_history,
    plot_tsb_zones,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_figures():
    """Close all matplotlib figures after each test."""
    yield
    matplotlib.pyplot.close("all")


def _make_tl(n: int = 30, trimp_value: float = 40.0) -> TrainingLoad:
    """Build a TrainingLoad with *n* days of constant TRIMP."""
    trimp = np.full(n, trimp_value, dtype=float)
    atl = compute_atl(trimp)
    ctl = compute_ctl(trimp)
    tsb = compute_tsb(ctl, atl)
    dates = [
        f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}" for i in range(n)
    ]
    return TrainingLoad(dates=dates, trimp=trimp, atl=atl, ctl=ctl, tsb=tsb)


def _make_sessions(dates: list[str], sport: str = "running") -> list[dict]:
    return [
        {
            "date": d,
            "trimp": 40.0,
            "duration_min": 60.0,
            "sport_type": sport,
            "notes": None,
        }
        for d in dates
    ]


_EMPTY_TL = TrainingLoad()

# ── plot_atl_ctl_tsb ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPlotAtlCtlTsb:
    """Tests for plot_atl_ctl_tsb()."""

    def test_returns_figure(self):
        """Must return a matplotlib Figure."""
        assert isinstance(plot_atl_ctl_tsb(_make_tl()), Figure)

    def test_has_two_axes(self):
        """Figure must have exactly two Axes (top + bottom panels)."""
        fig = plot_atl_ctl_tsb(_make_tl())
        assert len(fig.axes) == 2  # noqa: PLR2004

    def test_title_is_set(self):
        """Default title must appear in the figure."""
        fig = plot_atl_ctl_tsb(_make_tl(), title="My Title")
        assert fig._suptitle.get_text() == "My Title"

    def test_top_panel_has_two_lines(self):
        """Top axes must have ATL and CTL lines (2 line artists)."""
        fig = plot_atl_ctl_tsb(_make_tl())
        ax_top = fig.axes[0]
        lines = [
            child for child in ax_top.get_children() if hasattr(child, "get_xdata")
        ]
        assert len(lines) >= 2  # noqa: PLR2004

    def test_custom_figsize_accepted(self):
        """Custom figsize must not raise."""
        fig = plot_atl_ctl_tsb(_make_tl(), figsize=(8, 4))
        assert isinstance(fig, Figure)

    def test_raises_on_empty_training_load(self):
        """Empty TrainingLoad must raise ValueError."""
        with pytest.raises(ValueError, match="at least one day"):
            plot_atl_ctl_tsb(_EMPTY_TL)

    def test_single_day_accepted(self):
        """A one-day TrainingLoad must not raise."""
        tl = _make_tl(n=1)
        assert isinstance(plot_atl_ctl_tsb(tl), Figure)

    def test_long_series_accepted(self):
        """A 365-day series must not raise."""
        tl = _make_tl(n=31)  # stay within Jan to avoid date helper overflow
        assert isinstance(plot_atl_ctl_tsb(tl), Figure)


# ── plot_trimp_history ────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPlotTrimpHistory:
    """Tests for plot_trimp_history()."""

    def test_returns_figure(self):
        """Must return a matplotlib Figure."""
        assert isinstance(plot_trimp_history(_make_tl()), Figure)

    def test_has_one_axis(self):
        """Figure must have exactly one Axes."""
        fig = plot_trimp_history(_make_tl())
        assert len(fig.axes) == 1

    def test_title_is_set(self):
        """Custom title must appear on the axes."""
        fig = plot_trimp_history(_make_tl(), title="TRIMP Plot")
        assert fig.axes[0].get_title() == "TRIMP Plot"

    def test_bar_count_matches_days(self):
        """Number of bars must match the number of days in TrainingLoad."""
        tl = _make_tl(n=14)
        fig = plot_trimp_history(tl)
        bars = [p for p in fig.axes[0].patches]
        assert len(bars) == 14  # noqa: PLR2004

    def test_rolling_mean_drawn_for_long_series(self):
        """A 7-day rolling mean line must be present for series ≥ 7 days."""
        tl = _make_tl(n=20)
        fig = plot_trimp_history(tl)
        lines = fig.axes[0].get_lines()
        assert len(lines) >= 1

    def test_no_rolling_mean_for_short_series(self):
        """Series shorter than 7 days must not add a rolling mean line."""
        tl = _make_tl(n=5)
        fig = plot_trimp_history(tl)
        lines = fig.axes[0].get_lines()
        assert len(lines) == 0

    def test_sessions_accepted_without_error(self):
        """Passing sessions with sport_type must not raise."""
        tl = _make_tl(n=10)
        sessions = _make_sessions(tl.dates[:10])
        assert isinstance(plot_trimp_history(tl, sessions=sessions), Figure)

    def test_custom_sport_colors_accepted(self):
        """Custom sport_colors dict must not raise."""
        tl = _make_tl(n=10)
        sessions = _make_sessions(tl.dates[:10], sport="running")
        fig = plot_trimp_history(
            tl, sessions=sessions, sport_colors={"running": "#ff0000"}
        )
        assert isinstance(fig, Figure)

    def test_raises_on_empty_training_load(self):
        """Empty TrainingLoad must raise ValueError."""
        with pytest.raises(ValueError, match="at least one day"):
            plot_trimp_history(_EMPTY_TL)

    def test_zero_trimp_days_render_without_error(self):
        """Rest days (TRIMP = 0) must not cause rendering errors."""
        trimp = np.array([40.0, 0.0, 0.0, 30.0, 0.0])
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        tsb = compute_tsb(ctl, atl)
        tl = TrainingLoad(
            dates=[
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
            ],
            trimp=trimp,
            atl=atl,
            ctl=ctl,
            tsb=tsb,
        )
        assert isinstance(plot_trimp_history(tl), Figure)


# ── plot_trimp_history — multi-activity stacking ─────────────────────────────


@pytest.mark.unit
class TestPlotTrimpHistoryMultiActivity:
    """Tests for stacked-bar rendering when a day has multiple activities."""

    def _make_multi_day_tl(self) -> TrainingLoad:
        """TrainingLoad over 5 days; day 0 has two activities (30 + 40 = 70 TRIMP)."""
        trimp = np.array([70.0, 40.0, 35.0, 50.0, 0.0])
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        tsb = compute_tsb(ctl, atl)
        return TrainingLoad(
            dates=[
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
            ],
            trimp=trimp,
            atl=atl,
            ctl=ctl,
            tsb=tsb,
        )

    def _make_multi_sessions(self) -> list[dict]:
        """Two running+cycling sessions on 2026-01-01; one session on following days."""
        return [
            {
                "date": "2026-01-01",
                "trimp": 30.0,
                "duration_min": 45.0,
                "sport_type": "running",
                "notes": None,
            },
            {
                "date": "2026-01-01",
                "trimp": 40.0,
                "duration_min": 60.0,
                "sport_type": "cycling",
                "notes": None,
            },
            {
                "date": "2026-01-02",
                "trimp": 40.0,
                "duration_min": 60.0,
                "sport_type": "running",
                "notes": None,
            },
            {
                "date": "2026-01-03",
                "trimp": 35.0,
                "duration_min": 50.0,
                "sport_type": "cycling",
                "notes": None,
            },
            {
                "date": "2026-01-04",
                "trimp": 50.0,
                "duration_min": 70.0,
                "sport_type": "running",
                "notes": None,
            },
        ]

    def test_returns_figure(self):
        """Multi-activity sessions must return a Figure without error."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        assert isinstance(plot_trimp_history(tl, sessions=sessions), Figure)

    def test_extra_bar_for_stacked_day(self):
        """A day with 2 activities must produce 2 bar patches, not 1."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        # 3 active single-activity days + 2 bars stacked on day 0 + 0 for rest day = 5
        bars = fig.axes[0].patches
        assert len(bars) == 5  # noqa: PLR2004

    def test_stacked_bars_have_different_bottoms(self):
        """The two bars on the multi-activity day must have different y-origins."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        # Bars at x-position 0 are the stacked pair
        ax = fig.axes[0]
        bars_at_0 = [p for p in ax.patches if abs(p.get_x() + p.get_width() / 2) < 0.5]
        assert len(bars_at_0) == 2  # noqa: PLR2004
        bottoms = sorted(p.get_y() for p in bars_at_0)
        assert bottoms[0] == pytest.approx(0.0)
        assert bottoms[1] == pytest.approx(30.0)

    def test_stacked_total_height_equals_sum(self):
        """Heights of stacked bars must sum to the total daily TRIMP."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        ax = fig.axes[0]
        bars_at_0 = [p for p in ax.patches if abs(p.get_x() + p.get_width() / 2) < 0.5]
        total = sum(p.get_height() for p in bars_at_0)
        assert total == pytest.approx(70.0)

    def test_legend_shows_all_sport_types(self):
        """Legend must list every unique sport type present across all sessions."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        legend = fig.axes[0].get_legend()
        assert legend is not None
        labels = {t.get_text() for t in legend.get_texts()}
        assert "running" in labels
        assert "cycling" in labels

    def test_single_activity_day_unaffected(self):
        """Single-activity days in a mixed session list must draw one bar each."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        ax = fig.axes[0]
        # Day index 1 (2026-01-02) has one session — expect exactly one bar at x=1
        bars_at_1 = [
            p for p in ax.patches if abs(p.get_x() + p.get_width() / 2 - 1.0) < 0.5
        ]
        assert len(bars_at_1) == 1

    def test_rest_day_renders_no_bar(self):
        """A day with TRIMP = 0 and no sessions must produce no bar."""
        tl = self._make_multi_day_tl()
        sessions = self._make_multi_sessions()
        fig = plot_trimp_history(tl, sessions=sessions)
        ax = fig.axes[0]
        # Day index 4 (2026-01-05) is a rest day
        bars_at_4 = [
            p for p in ax.patches if abs(p.get_x() + p.get_width() / 2 - 4.0) < 0.5
        ]
        assert len(bars_at_4) == 0


# ── plot_tsb_zones ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestPlotTsbZones:
    """Tests for plot_tsb_zones()."""

    def test_returns_figure(self):
        """Must return a matplotlib Figure."""
        assert isinstance(plot_tsb_zones(_make_tl()), Figure)

    def test_has_one_axis(self):
        """Figure must have exactly one Axes."""
        fig = plot_tsb_zones(_make_tl())
        assert len(fig.axes) == 1

    def test_title_is_set(self):
        """Custom title must appear on the axes."""
        fig = plot_tsb_zones(_make_tl(), title="Zones")
        assert fig.axes[0].get_title() == "Zones"

    def test_tsb_line_is_present(self):
        """A TSB line artist must be present on the axes."""
        fig = plot_tsb_zones(_make_tl())
        lines = fig.axes[0].get_lines()
        assert len(lines) >= 1

    def test_legend_has_zone_labels(self):
        """Legend must list at least one TSB zone."""
        fig = plot_tsb_zones(_make_tl())
        legend = fig.axes[0].get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert len(labels) >= 1

    def test_raises_on_empty_training_load(self):
        """Empty TrainingLoad must raise ValueError."""
        with pytest.raises(ValueError, match="at least one day"):
            plot_tsb_zones(_EMPTY_TL)

    def test_custom_figsize_accepted(self):
        """Custom figsize must not raise."""
        assert isinstance(plot_tsb_zones(_make_tl(), figsize=(8, 4)), Figure)

    def test_positive_tsb_series_renders(self):
        """All-positive TSB (rested athlete) must render without error."""
        trimp = np.zeros(20)  # no training → CTL=ATL=0, TSB=0
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        tsb = compute_tsb(ctl, atl)
        tl = TrainingLoad(
            dates=[f"2026-01-{i + 1:02d}" for i in range(20)],
            trimp=trimp,
            atl=atl,
            ctl=ctl,
            tsb=tsb,
        )
        assert isinstance(plot_tsb_zones(tl), Figure)

    def test_deeply_negative_tsb_renders(self):
        """Very negative TSB (overload zone) must render without error."""
        trimp = np.full(30, 100.0)  # heavy daily load
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        tsb = compute_tsb(ctl, atl)
        tl = TrainingLoad(
            dates=[
                f"2026-01-{i + 1:02d}" if i < 31 else f"2026-02-{i - 30:02d}"
                for i in range(30)
            ],
            trimp=trimp,
            atl=atl,
            ctl=ctl,
            tsb=tsb,
        )
        assert isinstance(plot_tsb_zones(tl), Figure)
