"""Poor-quality sessions are flagged on the evolution charts (issue v0.4.0-03)."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from cardiolab.labels import LABELS_FR
from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.signals.quality import SignalQuality
from cardiolab.visualization._quality import mark_poor_sessions, poor_indices
from cardiolab.visualization.coherence_plots import plot_coherence_score_evolution
from cardiolab.visualization.dashboard_plots import (
    plot_readiness_evolution,
    plot_score_evolution,
)
from cardiolab.visualization.resting_plots import plot_resting_evolution
from cardiolab.visualization.vo2max_plots import plot_vo2max_evolution

GOOD = SignalQuality("good", 0.3, True, 300, 300.0)
POOR = SignalQuality("poor", 7.5, True, 300, 300.0)
POOR_LABELS = {"Poor signal quality", LABELS_FR["quality_poor_marker"]}


def _marked(fig) -> int:
    """Count the poor-quality crosses drawn on a figure."""
    return sum(
        len(c.get_offsets())
        for ax in fig.axes
        for c in ax.collections
        if c.get_label() in POOR_LABELS
    )


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


@pytest.mark.unit
class TestMarker:
    """mark_poor_sessions / poor_indices."""

    def test_poor_indices(self):
        """Only poor qualities are returned; None (unknown) is skipped."""
        assert poor_indices([GOOD, POOR, None, POOR]) == [1, 3]

    def test_no_marker_without_poor(self):
        """Nothing drawn, False returned, when no session is poor."""
        _, ax = plt.subplots()
        assert not mark_poor_sessions(ax, [0, 1], [1.0, 2.0], [GOOD, None])
        assert not ax.collections

    def test_translated_legend(self):
        """The legend entry follows the labels dict."""
        _, ax = plt.subplots()
        assert mark_poor_sessions(ax, [0, 1], [1.0, 2.0], [GOOD, POOR], LABELS_FR)
        assert ax.collections[-1].get_label() == "Signal de mauvaise qualité"


@pytest.mark.unit
class TestCharts:
    """Evolution charts flag poor sessions."""

    def _features(self) -> list[HRVFeatures]:
        return [
            HRVFeatures(
                date=f"2026-01-0{i}",
                rmssd=50.0 + i,
                mean_hr=60.0,
                score=60.0,
                quality=POOR if i == 2 else GOOD,
            )
            for i in range(1, 5)
        ]

    def test_resting_evolution(self):
        """RMSSD and score panels both flag the poor session."""
        features = self._features()
        fig = plot_resting_evolution(features, [f.score for f in features])
        assert _marked(fig) == 2

    def test_readiness_and_generic_score(self):
        """Readiness and generic score charts flag it once."""
        assert _marked(plot_readiness_evolution(self._features())) == 1
        assert _marked(plot_score_evolution(self._features())) == 1

    def test_coherence_and_vo2max(self):
        """Coherence and VO2max evolutions flag poor sessions."""
        coh = [
            CoherenceResult(coherence_score=50.0, quality=q) for q in (GOOD, POOR, None)
        ]
        vo2 = [
            VO2maxResult(vo2max_esco_flatt=45.0, vo2max_ln_rmssd=48.0, quality=q)
            for q in (POOR, GOOD)
        ]
        assert _marked(plot_coherence_score_evolution(coh)) == 1
        assert _marked(plot_vo2max_evolution(vo2)) == 1

    def test_no_quality_no_marker(self):
        """Sessions stored before v0.4.0 (no quality) are never flagged."""
        features = [HRVFeatures(rmssd=50.0, mean_hr=60.0, score=60.0) for _ in range(3)]
        assert _marked(plot_resting_evolution(features, [60.0] * 3)) == 0
