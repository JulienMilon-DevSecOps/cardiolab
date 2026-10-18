"""Tests for the signal quality index (issue v0.4.0-03) — cardiolab.signals.quality."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.datasets import load_sample
from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.quality import (
    ACCEPTABLE_MAX_PCT,
    GOOD_MAX_PCT,
    SignalQuality,
    grade_quality,
    quality_columns,
    signal_quality,
)
from cardiolab.signals.rr import RRSeries


def _clean(n: int = 400, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return 900 + 35 * np.sin(2 * np.pi * t / 4.2) + rng.normal(0, 12, n)


def _with_missed_beats(values: np.ndarray, positions: list[int]) -> np.ndarray:
    rr = list(values)
    for p in sorted(positions, reverse=True):
        rr[p : p + 2] = [rr[p] + rr[p + 1]]
    return np.asarray(rr)


def _quality(grade: str) -> SignalQuality:
    return SignalQuality(grade, 0.0, True, 300, 300.0)


# ======================
# Grading
# ======================


@pytest.mark.unit
class TestGrade:
    """Thresholds: good < 2 %, acceptable < 5 %, poor ≥ 5 %; uncorrected → poor."""

    @pytest.mark.parametrize(
        ("pct", "grade"),
        [
            (0.0, "good"),
            (1.99, "good"),
            (2.0, "acceptable"),
            (4.99, "acceptable"),
            (5.0, "poor"),
            (12.0, "poor"),
        ],
    )
    def test_corrected_thresholds(self, pct, grade):
        """Corrected recordings are graded on the share of corrected beats."""
        assert grade_quality(pct, corrected=True) == grade

    def test_default_thresholds(self):
        """Default thresholds are those of the issue."""
        assert (GOOD_MAX_PCT, ACCEPTABLE_MAX_PCT) == (2.0, 5.0)

    def test_uncorrected_artifact_is_poor(self):
        """One uncorrected artefact is enough to make the recording poor."""
        assert grade_quality(0.3, corrected=False) == "poor"

    def test_uncorrected_clean_is_good(self):
        """A clean, uncorrected recording is good."""
        assert grade_quality(0.0, corrected=False) == "good"

    def test_custom_thresholds(self):
        """Thresholds are configurable."""
        assert grade_quality(3.0, True, good_max=4.0, acceptable_max=8.0) == "good"
        assert grade_quality(9.0, True, good_max=4.0, acceptable_max=8.0) == "poor"


# ======================
# SignalQuality
# ======================


@pytest.mark.unit
class TestSignalQuality:
    """Construction and serialisation."""

    def test_from_counts(self):
        """Share and grade derived from counts."""
        q = SignalQuality.from_counts(300, 9, True, 301.27)
        assert q.artifact_pct == pytest.approx(3.0)
        assert q.grade == "acceptable"
        assert q.effective_duration == pytest.approx(301.3)
        assert not q.is_poor

    def test_dict_round_trip(self):
        """to_dict() → from_dict() gives back the same object; JSON-ready."""
        import json

        q = SignalQuality.from_counts(300, 20, True, 300.0)
        assert SignalQuality.from_dict(json.loads(json.dumps(q.to_dict()))) == q
        assert q.is_poor

    def test_from_dict_none(self):
        """No stored quality → None (unknown)."""
        assert SignalQuality.from_dict(None) is None

    def test_quality_columns(self):
        """Flat columns, None when unknown."""
        q = SignalQuality.from_counts(100, 1, True, 90.0)
        cols = quality_columns(q)
        assert cols["quality_grade"] == "good"
        assert cols["quality_artifact_pct"] == pytest.approx(1.0)
        assert set(quality_columns(None).values()) == {None}


# ======================
# signal_quality(rr)
# ======================


@pytest.mark.unit
class TestSignalQualityOfSeries:
    """Quality of an RRSeries, corrected or not."""

    def test_clean_series_good(self):
        """A clean series is good, even without correction."""
        q = signal_quality(RRSeries(_clean()))
        assert q.grade == "good"
        assert not q.corrected
        assert q.artifact_pct == 0.0

    def test_uncorrected_missed_beat_poor(self):
        """A missed beat left in the series makes it poor."""
        q = signal_quality(RRSeries(_with_missed_beats(_clean(), [100])))
        assert q.grade == "poor"
        assert not q.corrected
        assert q.artifact_pct > 0

    def test_corrected_series_uses_report(self):
        """After correct_artifacts(), the share of corrected beats grades it."""
        corrected, report = RRSeries(
            _with_missed_beats(_clean(), [100])
        ).correct_artifacts()
        q = signal_quality(corrected)
        assert q.corrected
        assert q.artifact_pct == pytest.approx(report.corrected_pct, abs=0.01)
        assert q.grade == "good"
        assert q.n_beats == len(corrected)

    def test_many_corrections_poor(self):
        """More than 5 % corrected beats → poor."""
        dirty = _with_missed_beats(_clean(n=300), list(range(30, 280, 12)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            corrected, _ = RRSeries(dirty).correct_artifacts()
        assert signal_quality(corrected).grade == "poor"

    def test_real_sample(self):
        """Sample 2026-04-24: poor raw (missed beat), good once corrected."""
        rr = load_sample("resting", 0)
        assert signal_quality(rr).grade == "poor"
        assert signal_quality(rr.correct_artifacts()[0]).grade == "good"


# ======================
# Protocols
# ======================


@pytest.mark.unit
class TestProtocols:
    """Protocols attach a quality index to their results."""

    def test_resting_auto_clean(self):
        """resting_hrv(auto_clean=True) → corrected, good."""
        f = resting_hrv(load_sample("resting", 0), auto_clean=True)
        assert f.quality.corrected
        assert f.quality.grade == "good"
        assert f.to_dict()["quality_grade"] == "good"

    def test_resting_without_auto_clean(self):
        """resting_hrv() on the raw sample → poor (uncorrected missed beat)."""
        assert resting_hrv(load_sample("resting", 0)).quality.grade == "poor"

    def test_orthostatic_quality_per_phase(self):
        """An artefact in the standing phase does not downgrade the supine phase."""
        rng = np.random.default_rng(1)
        supine = rng.normal(950, 15, 330)
        transition = np.linspace(950, 700, 40)
        standing = rng.normal(700, 12, 420)
        standing[200] *= 2.1  # long beat while standing, left uncorrected
        result = orthostatic_hrv(
            RRSeries(np.concatenate([supine, transition, standing])),
            min_phase_duration=60.0,
        )
        assert result.phases.supine.features.quality.grade == "good"
        assert result.phases.standing.features.quality.grade == "poor"
        assert result.quality.grade == "poor"

    def test_orthostatic_auto_clean(self):
        """Sample orthostatic test, corrected: every phase graded, overall good."""
        result = orthostatic_hrv(
            load_sample("orthostatic", 0), auto_clean=True, min_phase_duration=60.0
        )
        phases = result.phases
        for phase in (phases.supine, phases.transition, phases.standing):
            assert phase.features.quality.corrected
        assert result.quality.grade == "good"
        assert result.to_dict()["quality_grade"] == "good"


# ======================
# Baseline
# ======================


@pytest.mark.unit
class TestBaseline:
    """poor sessions are left out of the baseline by default."""

    def _history(self) -> list[HRVFeatures]:
        sessions = [
            HRVFeatures(
                date=f"2026-01-0{i}", rmssd=50.0, mean_hr=60.0, quality=_quality("good")
            )
            for i in range(1, 6)
        ]
        sessions.append(
            HRVFeatures(
                date="2026-01-06", rmssd=150.0, mean_hr=40.0, quality=_quality("poor")
            )
        )
        sessions.append(
            HRVFeatures(date="2026-01-07", rmssd=50.0, mean_hr=60.0)
        )  # unknown
        return sessions

    def test_poor_excluded_by_default(self):
        """The poor session does not move the statistics."""
        baseline = Baseline.from_features(self._history())
        assert baseline.median_rmssd() == pytest.approx(50.0)
        assert baseline.mean_hr() == pytest.approx(60.0)
        assert [s.date for s in baseline.excluded] == ["2026-01-06"]

    def test_unknown_quality_kept(self):
        """Sessions without quality (before v0.4.0) are kept."""
        baseline = Baseline.from_features(self._history())
        assert "2026-01-07" in [s.date for s in baseline.sessions]
        assert len(baseline.sessions) == 6

    def test_include_poor(self):
        """include_poor=True restores the previous behaviour."""
        baseline = Baseline.from_features(self._history(), include_poor=True)
        assert baseline.mean_hr() > 55.0
        assert baseline.excluded == []

    def test_rolling_skips_poor(self):
        """Rolling statistics skip poor sessions too."""
        baseline = Baseline(history=self._history(), window=3)
        assert max(baseline.rolling_rmssd()) == pytest.approx(50.0)
