"""Tests for RR artefact correction (Lipponen & Tarvainen 2019) — cardiolab.signals.artifacts."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from cardiolab.datasets import load_sample
from cardiolab.signals.artifacts import (
    MIN_BEATS,
    ArtifactReport,
    correct_artifacts,
    detect_artifacts,
)
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

# ======================
# Synthetic signals
# ======================


def _clean(n: int = 400, seed: int = 0) -> np.ndarray:
    """Realistic RR (ms): respiratory + slow oscillation + noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return (
        900
        + 35 * np.sin(2 * np.pi * t / 4.2)
        + 20 * np.sin(2 * np.pi * t / 25)
        + rng.normal(0, 12, n)
    )


def _athlete_rsa(n: int = 400, seed: int = 0) -> np.ndarray:
    """Slow heart (≈ 50 bpm) with a strong, sharp respiratory arrhythmia."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    wave = np.sin(2 * np.pi * t / 4.0)
    return 1180 + 70 * wave + 25 * np.sign(wave) + rng.normal(0, 15, n)


def _inject(clean: np.ndarray, seed: int, n_each: int = 3):
    """Inject ectopic / missed / extra / long beats; return (dirty, {index: kind})."""
    rng = np.random.default_rng(seed + 100)
    rr = list(clean)
    positions = sorted(
        rng.choice(np.arange(30, len(rr) - 30, 12), size=4 * n_each, replace=False),
        reverse=True,
    )
    kinds = ["ectopic", "missed", "extra", "long"] * n_each
    rng.shuffle(kinds)
    events = []
    for p, kind in zip(positions, kinds, strict=True):
        if kind == "ectopic":  # premature beat + compensatory pause
            early = 0.65 * rr[p]
            rr[p + 1] += rr[p] - early
            rr[p] = early
        elif kind == "missed":  # two intervals merged
            rr[p : p + 2] = [rr[p] + rr[p + 1]]
        elif kind == "extra":  # one interval split
            a = 0.4 * rr[p]
            rr[p : p + 1] = [a, rr[p] - a]
        else:  # abnormally long interval
            rr[p] *= 1.45
        events.append((p, kind))
    truth = {}
    for p, kind in events:
        shift = sum(
            -1 if k == "missed" else 1 if k == "extra" else 0
            for q, k in events
            if q < p
        )
        truth[p + shift] = kind
    return np.asarray(rr), truth


def _rmssd(x) -> float:
    return float(np.sqrt(np.mean(np.diff(np.asarray(x)) ** 2)))


# ======================
# Acceptance criteria (issue v0.4.0-01)
# ======================


@pytest.mark.unit
class TestAcceptance:
    """≥ 95 % of injected artefacts detected, RMSSD within ±5 %, clean untouched."""

    def test_detection_rate_and_rmssd(self):
        """20 series × 12 artefacts: detected ≥ 95 %, corrected RMSSD within 5 %."""
        events = detected = 0
        for seed in range(20):
            clean = _clean(seed=seed)
            dirty, truth = _inject(clean, seed)
            flagged = {i for v in detect_artifacts(dirty).values() for i in v}
            events += len(truth)
            detected += sum(1 for p in truth if {p - 1, p, p + 1} & flagged)
            corrected, _, _ = correct_artifacts(dirty)
            assert _rmssd(corrected) == pytest.approx(_rmssd(clean), rel=0.05)
        assert detected / events >= 0.95

    @pytest.mark.parametrize("seed", range(30))
    def test_clean_signal_unchanged(self, seed):
        """A clean recording is returned unchanged."""
        clean = _clean(seed=seed)
        corrected, _, report = correct_artifacts(clean)
        assert report.n_corrected == 0
        np.testing.assert_array_equal(corrected, clean)

    @pytest.mark.parametrize("seed", range(10))
    def test_athlete_respiratory_arrhythmia_kept(self, seed):
        """Sharp physiological swings of a trained athlete are not corrected."""
        _, _, report = correct_artifacts(_athlete_rsa(seed=seed))
        assert report.n_corrected == 0

    def test_amplitude_gate_is_what_protects_athletes(self):
        """Without the 20 % gate, the published rules flag the athlete's swings."""
        flagged = sum(
            correct_artifacts(_athlete_rsa(seed=s), min_deviation=0)[2].n_corrected
            for s in range(10)
        )
        assert flagged > 0


# ======================
# Classification
# ======================


@pytest.mark.unit
class TestClassification:
    """Each artefact type is recognised as such."""

    def test_missed_beat(self):
        """Two merged intervals → missed."""
        rr = list(_clean(seed=3))
        rr[100:102] = [rr[100] + rr[101]]
        assert 100 in detect_artifacts(np.asarray(rr))["missed"]

    def test_extra_beat(self):
        """One interval split in two → extra."""
        rr = list(_clean(seed=4))
        rr[100:101] = [0.4 * rr[100], 0.6 * rr[100]]
        assert 100 in detect_artifacts(np.asarray(rr))["extra"]

    def test_ectopic_beat(self):
        """Premature beat + compensatory pause → ectopic on the pair."""
        rr = _clean(seed=5)
        early = 0.65 * rr[100]
        rr[101] += rr[100] - early
        rr[100] = early
        assert {100, 101} & set(detect_artifacts(rr)["ectopic"])

    def test_long_beat(self):
        """Abnormally long interval → long/short."""
        rr = _clean(seed=6)
        rr[100] *= 1.45
        assert 100 in detect_artifacts(rr)["long_short"]


# ======================
# Corrections
# ======================


@pytest.mark.unit
class TestCorrections:
    """Corrections keep the series consistent."""

    def test_missed_beat_split_in_halves(self):
        """A missed beat adds one interval; total duration is kept."""
        rr = list(_clean(seed=7))
        rr[100:102] = [rr[100] + rr[101]]
        corrected, _, report = correct_artifacts(np.asarray(rr))
        assert report.missed == 1
        assert len(corrected) == len(rr) + 1
        assert corrected.sum() == pytest.approx(sum(rr))

    def test_extra_beat_merged(self):
        """An extra beat removes one interval; total duration is kept."""
        rr = list(_clean(seed=8))
        rr[100:101] = [0.4 * rr[100], 0.6 * rr[100]]
        corrected, _, report = correct_artifacts(np.asarray(rr))
        assert report.extra == 1
        assert len(corrected) == len(rr) - 1
        assert corrected.sum() == pytest.approx(sum(rr))

    def test_timestamps_follow_added_and_removed_beats(self):
        """Timestamps stay aligned (one per interval, increasing, same end)."""
        dirty, _ = _inject(_clean(seed=9), seed=9)
        ts = np.cumsum(dirty) / 1000.0
        corrected, new_ts, _ = correct_artifacts(dirty, ts)
        assert len(new_ts) == len(corrected)
        assert np.all(np.diff(new_ts) > 0)
        assert new_ts[-1] == pytest.approx(ts[-1])

    def test_input_not_modified(self):
        """The input array is never modified in place."""
        dirty, _ = _inject(_clean(seed=10), seed=10)
        before = dirty.copy()
        correct_artifacts(dirty)
        np.testing.assert_array_equal(dirty, before)


# ======================
# Edge cases and report
# ======================


@pytest.mark.unit
class TestEdgeCases:
    """Short, constant and multi-pass cases."""

    def test_short_series_untouched(self):
        """Fewer than MIN_BEATS intervals: no detection, no pass."""
        rr = np.array([800.0] * (MIN_BEATS - 1))
        rr[3] = 1600.0
        corrected, _, report = correct_artifacts(rr)
        assert report.passes == 0
        np.testing.assert_array_equal(corrected, rr)

    def test_constant_series(self):
        """A perfectly constant series does not crash and is not corrected."""
        _, _, report = correct_artifacts(np.full(100, 850.0))
        assert report.n_corrected == 0

    def test_max_passes(self):
        """More passes never report fewer corrections than one pass."""
        dirty, _ = _inject(_clean(seed=11), seed=11)
        one = correct_artifacts(dirty, max_passes=1)[2]
        three = correct_artifacts(dirty, max_passes=3)[2]
        assert one.passes == 1
        assert three.n_corrected >= one.n_corrected


@pytest.mark.unit
class TestReport:
    """ArtifactReport fields."""

    def test_counts_and_percentage(self):
        """Percentage of corrected beats and reliability flag."""
        report = ArtifactReport(n_input=200, n_output=200, ectopic=4, long_short=2)
        assert report.n_corrected == 6
        assert report.corrected_pct == pytest.approx(3.0)
        assert report.is_reliable

    def test_unreliable_above_5_percent(self):
        """More than 5 % corrected → not reliable."""
        assert not ArtifactReport(n_input=100, n_output=100, missed=6).is_reliable

    def test_to_dict(self):
        """to_dict() gives a JSON-ready summary."""
        d = ArtifactReport(n_input=100, n_output=101, missed=1, passes=1).to_dict()
        assert d["method"] == "lipponen2019"
        assert d["n_corrected"] == 1
        assert d["corrected_pct"] == 1.0


# ======================
# RRSeries.correct_artifacts()
# ======================


@pytest.mark.unit
class TestRRSeriesMethod:
    """The RRSeries wrapper."""

    def test_returns_new_series_and_report(self):
        """A new RRSeries is returned with the report in its metadata."""
        dirty, _ = _inject(_clean(seed=12), seed=12)
        rr = RRSeries(dirty, metadata={"id": "x"})
        corrected, report = rr.correct_artifacts()
        assert isinstance(corrected, RRSeries)
        assert corrected is not rr
        assert corrected.metadata["id"] == "x"
        assert corrected.metadata["artifact_correction"] == report.to_dict()

    def test_unknown_method(self):
        """Unknown method → ValueError."""
        with pytest.raises(ValueError, match="Unknown artefact correction method"):
            RRSeries(_clean()).correct_artifacts(method="kubios")

    def test_warning_above_5_percent(self):
        """Too many corrected beats → PhysiologicalWarning."""
        dirty, _ = _inject(_clean(n=260, seed=13), seed=13, n_each=4)  # ~6 %
        with pytest.warns(PhysiologicalWarning, match="unreliable"):
            RRSeries(dirty).correct_artifacts()

    def test_no_warning_on_clean_signal(self):
        """A clean signal raises no warning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", PhysiologicalWarning)
            RRSeries(_clean()).correct_artifacts()

    def test_real_sample_missed_beat(self):
        """Sample 2026-04-24 (Polar H10): its 1 718 ms missed beat is split."""
        rr = load_sample("resting", 0)
        corrected, report = rr.correct_artifacts()
        assert report.missed == 1
        assert len(corrected) == len(rr) + 1
        assert corrected.intervals.max() < 1500
        assert _rmssd(corrected.intervals) < 0.6 * _rmssd(rr.intervals)
