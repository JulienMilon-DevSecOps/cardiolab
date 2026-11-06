"""Tests for cardiolab.visualization.dfa_threshold_plots and lsct_plots."""

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure

matplotlib.use("Agg")

from cardiolab.analytics.zones import five_zones, three_zones
from cardiolab.labels import LABELS_FR
from cardiolab.protocols.dfa_thresholds import dfa_thresholds
from cardiolab.protocols.lsct import lsct
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries
from cardiolab.visualization.dfa_threshold_plots import (
    plot_alpha1_vs_hr,
    plot_dfa_alpha1,
    plot_threshold_evolution,
    plot_training_zones,
)
from cardiolab.visualization.lsct_plots import plot_lsct_evolution, plot_lsct_session
from tests.protocols.test_dfa_thresholds import _power, _ramp_test
from tests.protocols.test_lsct import HR_MAX, _session

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def thresholds():
    """Thresholds of the synthetic ramp test, with power."""
    return dfa_thresholds(
        RRSeries(_ramp_test(minutes=16)), intensity=_power(16), intensity_unit="W"
    )


@pytest.fixture
def lsct_test():
    """Series and result of a synthetic LSCT."""
    t, hr, pw = _session()
    return t, hr, pw, lsct(t, hr, pw, HR_MAX, start_sec=300.0, date="2099-11-06")


# ── DFA thresholds ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestDfaThresholdPlots:
    """α1 over time, α1 against HR, threshold evolution."""

    def test_alpha1_over_time(self, thresholds):
        """Two axes (α1, HR) and a vertical line per detected threshold."""
        fig = plot_dfa_alpha1(thresholds, labels=LABELS_FR)
        assert isinstance(fig, Figure)
        assert len(fig.axes) == 2
        texts = [t.get_text() for t in fig.axes[0].texts]
        assert any(t.startswith("Seuil 1") and "W" in t for t in texts)

    def test_alpha1_vs_hr(self, thresholds):
        """Scatter of the windows up to the peak heart rate."""
        fig = plot_alpha1_vs_hr(thresholds)
        assert len(fig.axes[0].collections) == 1

    def test_evolution(self, thresholds):
        """One point per test; intensity axis when the unit is known."""
        fig = plot_threshold_evolution([thresholds, thresholds], ["d1", "d2"])
        assert len(fig.axes) == 2

    def test_evolution_errors(self, thresholds):
        """Empty list or label length mismatch."""
        with pytest.raises(ValueError):
            plot_threshold_evolution([])
        with pytest.raises(ValueError):
            plot_threshold_evolution([thresholds], ["a", "b"])

    def test_wrong_type(self):
        """Only a DFAThresholdsResult is accepted."""
        with pytest.raises(TypeError):
            plot_dfa_alpha1(object())


@pytest.mark.unit
class TestTrainingZonesPlot:
    """Horizontal zones scale."""

    @pytest.mark.parametrize(
        ("zones", "n"),
        [(five_zones(145, 168, 188), 5), (three_zones(145, 168, 188), 3)],
    )
    def test_one_bar_per_zone(self, zones, n):
        """One coloured bar per zone, translated names."""
        fig = plot_training_zones(zones, labels=LABELS_FR)
        assert len(fig.axes[0].patches) == n
        assert any("Z1" in t.get_text() for t in fig.axes[0].texts)

    def test_empty(self):
        """No zones: error."""
        with pytest.raises(ValueError):
            plot_training_zones([])


# ── LSCT ──────────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLsctPlots:
    """One test and the evolution."""

    def test_session(self, lsct_test):
        """Two panels, stage means annotated."""
        t, hr, pw, res = lsct_test
        fig = plot_lsct_session(t, hr, pw, res, labels=LABELS_FR)
        assert len(fig.axes) == 2
        assert any("280 W" in x.get_text() for x in fig.axes[1].texts)

    def test_session_errors(self, lsct_test):
        """Wrong result type, length mismatch."""
        t, hr, pw, res = lsct_test
        with pytest.raises(TypeError):
            plot_lsct_session(t, hr, pw, object())
        with pytest.raises(ValueError):
            plot_lsct_session(t, hr[:-1], pw, res)

    def test_evolution_marks_missed_target(self, lsct_test):
        """A test whose stage 3 target was not reached gets a cross."""
        t, hr, pw, res = lsct_test
        with pytest.warns(PhysiologicalWarning, match="Stage 3"):
            missed = lsct(
                t, hr * np.where(t >= 1020, 0.94, 1.0), pw, HR_MAX, start_sec=300.0
            )
        fig = plot_lsct_evolution([res, missed])
        labels = [line.get_label() for line in fig.axes[0].lines]
        assert "Stage 3 target not reached" in labels

    def test_evolution_errors(self, lsct_test):
        """Empty list or label length mismatch."""
        *_, res = lsct_test
        with pytest.raises(ValueError):
            plot_lsct_evolution([])
        with pytest.raises(ValueError):
            plot_lsct_evolution([res], ["a", "b"])
