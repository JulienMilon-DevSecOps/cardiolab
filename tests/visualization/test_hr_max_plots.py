"""Tests for cardiolab.visualization.hr_max_plots."""

import warnings

import matplotlib
import pytest
from matplotlib.figure import Figure

matplotlib.use("Agg")

from cardiolab.analytics.hr_max import observed_hr_max
from cardiolab.labels import LABELS_FR
from cardiolab.protocols.hr_max_test import hr_max_test
from cardiolab.visualization.hr_max_plots import plot_hr_max_history, plot_hr_max_test
from tests.protocols.test_hr_max_test import _test_session


def _result(**kwargs):
    t, hr = _test_session(**kwargs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = hr_max_test(
            t, hr, sport="running", sensor="chest_strap", date="2026-09-02"
        )
    return t, hr, res


class TestPlotHRMaxTest:
    """One field test."""

    def test_figure_and_legend(self):
        """Raw, held, final effort, retained peak, spike, profile."""
        t, hr, res = _result(spike_at=1500)
        fig = plot_hr_max_test(t, hr, res, profile_hr_max=185)
        assert isinstance(fig, Figure)
        legend = [x.get_text() for x in fig.axes[0].get_legend().get_texts()]
        assert legend[0] == "Heart rate"
        assert any(x.startswith("HRmax retained: ") for x in legend)
        assert "Spike set aside (artefact)" in legend
        assert "Profile HRmax: 185 bpm" in legend

    def test_french(self):
        """French labels."""
        t, hr, res = _result()
        fig = plot_hr_max_test(t, hr, res, labels=LABELS_FR)
        assert fig._suptitle.get_text() == "Test de FC max"
        assert fig.axes[0].get_xlabel() == LABELS_FR["time_min"]


class TestPlotHRMaxHistory:
    """HRmax over time per sport."""

    def test_tests_and_observed(self):
        """Tests, observed value, profile line."""
        t, hr, res = _result()
        seen = observed_hr_max(
            [
                {
                    "time_sec": t,
                    "heart_rate": hr - 3,
                    "sport": "cycling",
                    "date": "2026-09-06",
                }
            ]
        )
        fig = plot_hr_max_history([res], observed=seen, profile_hr_max=185)
        legend = [x.get_text() for x in fig.axes[0].get_legend().get_texts()]
        assert legend[0] == "Running"
        assert "Observed in sessions" in legend

    def test_nothing_to_plot(self):
        """Only an invalid test: nothing dated to plot."""
        _, _, res = _result()
        res.status = "invalid"
        with pytest.raises(ValueError, match="No dated"):
            plot_hr_max_history([res])
