"""Signal quality column in the history tables (issue v0.4.0-03)."""

from __future__ import annotations

import pytest

from cardiolab.labels import LABELS_FR
from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.reporting.coherence import table_coherence_history
from cardiolab.reporting.resting import table_resting_history
from cardiolab.reporting.vo2max import table_vo2max_history
from cardiolab.signals.quality import SignalQuality

POOR = SignalQuality("poor", 7.5, True, 300, 300.0)
GOOD = SignalQuality("good", 0.0, True, 300, 300.0)


@pytest.mark.unit
class TestQualityColumn:
    """quality_grade is shown, coloured, translated; unknown → n/a."""

    def test_resting(self):
        """Resting history: grade per session, translated and coloured."""
        features = [
            HRVFeatures(date="2026-01-01", rmssd=50.0, mean_hr=60.0, quality=POOR),
            HRVFeatures(date="2026-01-02", rmssd=55.0, mean_hr=58.0),
        ]
        styler = table_resting_history(features, labels=LABELS_FR)
        grades = styler.data["quality_grade"]
        assert grades.iloc[0] == "poor"
        assert grades.isna().iloc[1]
        html = styler.to_html()
        assert "Mauvaise" in html
        assert "n/a" in html
        assert "#fadbd8" in html

    def test_coherence_and_vo2max(self):
        """Coherence and VO2max histories carry the grade too."""
        coh = table_coherence_history(
            [CoherenceResult(date="2026-01-01", quality=GOOD)]
        )
        vo2 = table_vo2max_history([VO2maxResult(date="2026-01-01", quality=POOR)])
        assert coh.data["quality_grade"].iloc[0] == "good"
        assert vo2.data["quality_grade"].iloc[0] == "poor"
