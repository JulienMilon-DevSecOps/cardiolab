"""Tests for cardiolab.visualization.statistical_plots."""

from datetime import date, timedelta

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure

matplotlib.use("Agg")

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.multivariate import anomaly_report
from cardiolab.labels import LABELS_FR
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.visualization.statistical_plots import (
    TREND_COLORS,
    plot_anomaly_timeline,
    plot_trend_overlay,
)
from tests.analytics.test_multivariate import _DAY0, _MEAN, _history, _session

pd = pytest.importorskip("pandas")

START = date(2026, 6, 1)


def _dated(values) -> list[tuple[str, float]]:
    return [((START + timedelta(days=i)).isoformat(), v) for i, v in enumerate(values)]


def _legend(fig: Figure, ax_index: int = 0) -> list[str]:
    return [t.get_text() for t in fig.axes[ax_index].get_legend().get_texts()]


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def report():
    """60 usual mornings, one sick morning, one session without DFA α1."""
    history = _history(60)
    history.append(
        _session(_MEAN + np.array([-0.8, 12.0, -0.5, 0.0]), _DAY0 + timedelta(days=60))
    )
    history[50].dfa_alpha1 = 0.0
    return anomaly_report(history)


# ── plot_anomaly_timeline ─────────────────────────────────────────────────────


class TestAnomalyTimeline:
    """Distance, threshold, unusual sessions, deviation of each metric."""

    def test_returns_figure_with_metric_panel(self, report):
        """Distance panel + one row per metric + colour bar."""
        fig = plot_anomaly_timeline(report)
        assert isinstance(fig, Figure)
        assert len(fig.axes) == 2  # distance, metrics
        assert len(fig.axes[1].child_axes) == 1  # colour bar
        assert [t.get_text() for t in fig.axes[1].get_yticklabels()] == [
            "ln_rmssd",
            "mean_hr",
            "dfa_alpha1",
            "sd_ratio",
        ]

    def test_legend_lists_every_state(self, report):
        """Building period, distance, threshold, unusual and unchecked sessions."""
        legend = _legend(plot_anomaly_timeline(report))
        assert legend == [
            "Reference building (too few sessions)",
            "Distance to usual sessions",
            "Alert threshold",
            "Unusual session",
            "Not checked (missing metric)",
        ]

    def test_unusual_session_marked(self, report):
        """The sick morning is a diamond at its distance."""
        fig = plot_anomaly_timeline(report)
        diamonds = [
            c for c in fig.axes[0].collections if c.get_label() == "Unusual session"
        ][0]
        assert report["mahalanobis"].iloc[-1] in diamonds.get_offsets()[:, 1]

    def test_french_labels(self, report):
        """Translated title and labels."""
        fig = plot_anomaly_timeline(report, labels=LABELS_FR)
        assert fig._suptitle.get_text() == LABELS_FR["anomaly_timeline_title"]
        assert "Mesure inhabituelle" in _legend(fig)
        assert fig.axes[1].get_yticklabels()[0].get_text() == "ln(RMSSD)"

    def test_without_metric_columns(self, report):
        """Only the distance panel when there is no z_<metric> column."""
        fig = plot_anomaly_timeline(
            report.drop(columns=[c for c in report if c.startswith("z_")])
        )
        assert len(fig.axes) == 1

    def test_only_insufficient_data(self):
        """Too few sessions: the figure is still drawn."""
        fig = plot_anomaly_timeline(anomaly_report(_history(10)))
        assert _legend(fig) == ["Reference building (too few sessions)"]

    @pytest.mark.parametrize("drop", ["mahalanobis", "status"])
    def test_not_a_report(self, report, drop):
        """A required column is missing."""
        with pytest.raises(ValueError, match="anomaly_report"):
            plot_anomaly_timeline(report.drop(columns=[drop]))

    def test_empty_report(self, report):
        """No session."""
        with pytest.raises(ValueError, match="no session"):
            plot_anomaly_timeline(report.iloc[:0])


# ── plot_trend_overlay ────────────────────────────────────────────────────────


class TestTrendOverlay:
    """Values, trend line per window, confidence band, sustained decline."""

    def _decline(self):
        rng = np.random.default_rng(3)
        return _dated(
            list(
                np.r_[np.full(56, 55.0), np.linspace(53, 38, 28)] + rng.normal(0, 1, 84)
            )
        )

    def test_one_line_per_window(self):
        """Whole period and 28 days: two coloured lines and one band entry."""
        fig = plot_trend_overlay(self._decline(), windows=(None, 28))
        legend = _legend(fig)
        assert legend[0] == "Sessions"
        assert legend[1].startswith("Whole-period trend: ")
        assert any(t.startswith("28-day trend: ") and "decreasing" in t for t in legend)
        assert sum("confidence band" in t for t in legend) == 1
        colors = [ln.get_color() for ln in fig.axes[0].get_lines()[1:]]
        assert colors == [TREND_COLORS["decreasing"]] * 2

    def test_stable_trend(self):
        """Pure noise: blue line, 'no clear trend'."""
        rng = np.random.default_rng(0)
        fig = plot_trend_overlay(_dated(list(50 + rng.normal(0, 3, 40))))
        assert "no clear trend" in _legend(fig)[1]
        assert fig.axes[0].get_lines()[1].get_color() == TREND_COLORS["stable"]

    def test_sustained_decline_highlighted(self):
        """The last values below the usual range are ringed."""
        legend = _legend(plot_trend_overlay(self._decline()))
        assert any(t.startswith("Below the usual range for ") for t in legend)
        legend = _legend(plot_trend_overlay(self._decline(), show_decline=False))
        assert not any(t.startswith("Below the usual range") for t in legend)

    def test_insufficient_window(self):
        """A window with fewer than 5 values is listed, without a line."""
        fig = plot_trend_overlay(_dated([50, 51, 49, 52, 50, 51, 50]), windows=(3,))
        assert _legend(fig)[1] == "3-day trend: too few values"

    def test_sessions_and_metric(self):
        """Baseline of HRVFeatures, metric read on the sessions, French labels."""
        sessions = [
            HRVFeatures(date=d, rmssd=60.0 - 0.2 * i, score=50.0)
            for i, (d, _) in enumerate(_dated([0] * 30))
        ]
        fig = plot_trend_overlay(
            Baseline.from_features(sessions), metric="rmssd", labels=LABELS_FR
        )
        assert fig.axes[0].get_ylabel() == LABELS_FR["rmssd"]
        assert "baisse nette" in _legend(fig)[1]
        assert "/semaine" in _legend(fig)[1]

    def test_end(self):
        """Values after end are not shown."""
        fig = plot_trend_overlay(self._decline(), end=START + timedelta(days=40))
        assert len(fig.axes[0].collections[0].get_offsets()) == 41

    def test_errors(self):
        """No dated value; no window."""
        with pytest.raises(ValueError, match="No dated value"):
            plot_trend_overlay([])
        with pytest.raises(ValueError, match="window"):
            plot_trend_overlay(_dated([1, 2, 3, 4, 5]), windows=())
