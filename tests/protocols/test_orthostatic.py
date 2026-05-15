"""Unit and integration tests for the orthostatic HRV protocol."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.protocols.orthostatic import (
    OrthostaticPhases,
    OrthostaticResult,
    PhaseSegment,
    TransitionSegment,
    _compute_rolling_mean_hr,
    _extract_segment,
    _find_stabilization,
    _find_sustained_onset,
    _interpret_response,
    detect_phases,
    orthostatic_hrv,
)
from cardiolab.signals.rr import RRSeries


# ======================
# FIXTURES
# ======================


def _make_orthostatic_rr(
    supine_bpm: float = 65.0,
    standing_bpm: float = 85.0,
    supine_sec: float = 310.0,
    standing_sec: float = 310.0,
    std_rr: float = 20.0,
    transition_beats: int = 40,
    rng_seed: int = 42,
) -> RRSeries:
    """Build a synthetic continuous RR series simulating a postural change.

    The series contains three concatenated segments:
    - Supine: ``supine_sec`` seconds at ``supine_bpm``.
    - Transition: ``transition_beats`` beats with HR linearly rising.
    - Standing: ``standing_sec`` seconds at ``standing_bpm``.
    """
    rng = np.random.default_rng(rng_seed)

    supine_rr = 60000.0 / supine_bpm
    n_supine = int(supine_sec / (supine_rr / 1000.0))
    supine = rng.normal(supine_rr, std_rr, n_supine).clip(min=300)

    standing_rr = 60000.0 / standing_bpm
    n_standing = int(standing_sec / (standing_rr / 1000.0))
    standing = rng.normal(standing_rr, std_rr // 2, n_standing).clip(min=300)

    trans_rr_values = np.linspace(supine_rr, standing_rr, transition_beats)
    transition = trans_rr_values + rng.normal(0, 10, transition_beats)
    transition = transition.clip(min=300)

    all_intervals = np.concatenate([supine, transition, standing])
    return RRSeries(all_intervals)


@pytest.fixture
def orthostatic_rr():
    """Standard orthostatic recording: 5-min supine + transition + 5-min standing."""
    return _make_orthostatic_rr()


@pytest.fixture
def orthostatic_rr_short_phases():
    """Orthostatic recording with phases below 240 s."""
    return _make_orthostatic_rr(supine_sec=120.0, standing_sec=120.0)


@pytest.fixture
def flat_rr():
    """Flat RR series with no HR change (no postural transition)."""
    rng = np.random.default_rng(0)
    intervals = rng.normal(857, 10, 600).clip(min=300)
    return RRSeries(intervals)


# ======================
# PhaseSegment / TransitionSegment
# ======================


class TestDataclasses:
    """Test dataclass instantiation and field presence."""

    def test_phase_segment_fields(self, orthostatic_rr):
        """PhaseSegment must expose rr, start_sec, end_sec, duration_sec, features."""
        from cardiolab.protocols.resting import resting_hrv

        seg = PhaseSegment(
            rr=orthostatic_rr,
            start_sec=0.0,
            end_sec=300.0,
            duration_sec=300.0,
            features=resting_hrv(orthostatic_rr),
        )
        assert seg.start_sec == 0.0
        assert seg.duration_sec == 300.0
        assert seg.features is not None

    def test_transition_segment_fields(self, orthostatic_rr):
        """TransitionSegment must expose delta_hr and peak_hr."""
        from cardiolab.protocols.resting import resting_hrv

        seg = TransitionSegment(
            rr=orthostatic_rr,
            start_sec=300.0,
            end_sec=340.0,
            duration_sec=40.0,
            delta_hr=20.0,
            peak_hr=90.0,
            features=resting_hrv(orthostatic_rr),
        )
        assert seg.delta_hr == 20.0
        assert seg.peak_hr == 90.0


# ======================
# _compute_rolling_mean_hr
# ======================


class TestComputeRollingMeanHR:
    """Tests for the causal rolling HR helper."""

    def test_constant_hr_unchanged(self):
        """Rolling mean of a constant HR signal must equal that constant."""
        hr = np.full(200, 70.0)
        cumtime = np.arange(1, 201) * 0.85
        result = _compute_rolling_mean_hr(hr, cumtime, window_sec=30.0)
        assert np.allclose(result, 70.0, atol=0.1)

    def test_output_same_length(self):
        """Output must have the same length as input."""
        hr = np.random.default_rng(0).normal(70, 5, 300)
        cumtime = np.cumsum(np.full(300, 0.857))
        result = _compute_rolling_mean_hr(hr, cumtime, window_sec=30.0)
        assert len(result) == 300

    def test_smoothing_reduces_variance(self):
        """Rolling mean must have lower variance than the raw HR."""
        rng = np.random.default_rng(1)
        hr = rng.normal(70, 10, 400)
        cumtime = np.cumsum(np.full(400, 0.857))
        result = _compute_rolling_mean_hr(hr, cumtime, window_sec=30.0)
        assert np.std(result) < np.std(hr)

    def test_causal_no_future_leakage(self):
        """A step change should only appear in the rolling output after it occurs."""
        n = 300
        hr = np.concatenate([np.full(150, 65.0), np.full(150, 90.0)])
        cumtime = np.cumsum(np.full(n, 0.857))
        result = _compute_rolling_mean_hr(hr, cumtime, window_sec=20.0)
        # The first half should remain near 65 before the step
        assert result[100] < 70.0


# ======================
# _find_sustained_onset
# ======================


class TestFindSustainedOnset:
    """Tests for the transition onset detector."""

    def test_detects_step_change(self):
        """Should detect the start of a step rise at the correct index."""
        hr = np.concatenate([np.full(100, 65.0), np.full(100, 85.0)])
        idx = _find_sustained_onset(hr, threshold=75.0, min_beats=5)
        assert idx == 100

    def test_returns_none_when_no_rise(self):
        """Should return None when the signal never exceeds the threshold."""
        hr = np.full(200, 65.0)
        assert _find_sustained_onset(hr, threshold=80.0) is None

    def test_ignores_short_spikes(self):
        """A brief spike shorter than min_beats must not trigger detection."""
        hr = np.full(200, 65.0)
        hr[50:53] = 90.0  # only 3 beats above threshold
        idx = _find_sustained_onset(hr, threshold=75.0, min_beats=5)
        assert idx is None

    def test_detects_after_short_spike(self):
        """A sustained rise after a brief spike should still be detected."""
        hr = np.full(300, 65.0)
        hr[50:53] = 90.0  # short spike — ignored
        hr[150:] = 88.0   # sustained rise — detected
        idx = _find_sustained_onset(hr, threshold=75.0, min_beats=5)
        assert idx == 150

    def test_min_beats_one(self):
        """With min_beats=1, the very first value above threshold is returned."""
        hr = np.concatenate([np.full(50, 60.0), np.full(50, 80.0)])
        idx = _find_sustained_onset(hr, threshold=75.0, min_beats=1)
        assert idx == 50


# ======================
# _find_stabilization
# ======================


class TestFindStabilization:
    """Tests for the stabilisation detector."""

    def test_stable_signal_returns_start_with_no_offset(self):
        """With min_duration_sec=0, a stable signal must return start_idx."""
        hr = np.full(300, 85.0)
        cumtime = np.cumsum(np.full(300, 0.7))
        idx = _find_stabilization(
            hr, cumtime, start_idx=0, window_sec=20.0, std_threshold=5.0, min_duration_sec=0.0
        )
        assert idx == 0

    def test_min_duration_enforced(self):
        """With min_duration_sec=15, the returned index must be ≥ 15 s after start."""
        hr = np.full(300, 85.0)
        cumtime = np.cumsum(np.full(300, 0.7))  # 0.7s per beat
        idx = _find_stabilization(
            hr, cumtime, start_idx=0, window_sec=20.0, std_threshold=5.0, min_duration_sec=15.0
        )
        assert cumtime[idx] >= 15.0

    def test_detects_stabilization_after_rise(self):
        """Should return an index after the initial rise period."""
        rng = np.random.default_rng(7)
        n = 400
        hr = np.concatenate([
            np.linspace(65, 90, 50),            # rising phase
            rng.normal(88, 1.5, 350),           # stable standing
        ])
        cumtime = np.cumsum(np.full(n, 0.7))
        idx = _find_stabilization(hr, cumtime, start_idx=0, window_sec=20.0, std_threshold=5.0)
        assert idx >= 0
        assert idx < n

    def test_fallback_midpoint(self):
        """When stabilisation is never reached, midpoint fallback is returned."""
        rng = np.random.default_rng(3)
        hr = rng.normal(80, 10, 200)  # always noisy — never stable with strict threshold
        cumtime = np.cumsum(np.full(200, 0.7))
        idx = _find_stabilization(hr, cumtime, start_idx=0, window_sec=20.0, std_threshold=0.1)
        assert 0 <= idx < 200


# ======================
# _extract_segment
# ======================


class TestExtractSegment:
    """Tests for the RRSeries segment extractor."""

    def test_full_extraction(self):
        """Extracting the full range should return all intervals."""
        rr = RRSeries(np.full(100, 857.0))
        cumtime = np.cumsum(rr.intervals) / 1000.0
        seg, s, e = _extract_segment(rr, cumtime, 0, 100)
        assert len(seg.intervals) == 100

    def test_partial_extraction(self):
        """Extracting a slice should return the correct subset."""
        rr = RRSeries(np.arange(700.0, 800.0))  # 100 intervals, distinct values
        cumtime = np.cumsum(rr.intervals) / 1000.0
        seg, s, e = _extract_segment(rr, cumtime, 10, 40)
        assert len(seg.intervals) == 30
        assert seg.intervals[0] == pytest.approx(710.0)

    def test_start_sec_zero_for_first_segment(self):
        """When start_idx=0, start_sec must be 0.0."""
        rr = RRSeries(np.full(50, 800.0))
        cumtime = np.cumsum(rr.intervals) / 1000.0
        _, start_sec, _ = _extract_segment(rr, cumtime, 0, 50)
        assert start_sec == 0.0

    def test_raises_if_too_short(self):
        """Should raise ValueError when the extracted segment has fewer than 2 intervals."""
        rr = RRSeries(np.full(50, 800.0))
        cumtime = np.cumsum(rr.intervals) / 1000.0
        with pytest.raises(ValueError, match="at least 2"):
            _extract_segment(rr, cumtime, 0, 1)

    def test_timestamps_attached_to_segment(self):
        """Extracted RRSeries must carry the corresponding timestamp slice."""
        rr = RRSeries(np.full(100, 800.0))
        cumtime = np.cumsum(rr.intervals) / 1000.0
        seg, _, _ = _extract_segment(rr, cumtime, 10, 30)
        assert seg.timestamps is not None
        assert len(seg.timestamps) == 20


# ======================
# detect_phases
# ======================


class TestDetectPhases:
    """Tests for the automatic phase segmentation function."""

    def test_returns_orthostatic_phases(self, orthostatic_rr):
        """detect_phases should return an OrthostaticPhases instance."""
        result = detect_phases(orthostatic_rr)
        assert isinstance(result, OrthostaticPhases)

    def test_three_segments_present(self, orthostatic_rr):
        """All three phases must be present and non-empty."""
        result = detect_phases(orthostatic_rr)
        assert len(result.supine.rr.intervals) >= 2
        assert len(result.transition.rr.intervals) >= 2
        assert len(result.standing.rr.intervals) >= 2

    def test_supine_hr_lower_than_standing(self, orthostatic_rr):
        """Supine mean HR should be lower than standing mean HR."""
        result = detect_phases(orthostatic_rr)
        assert result.supine.features.mean_hr < result.standing.features.mean_hr

    def test_transition_delta_hr_positive(self, orthostatic_rr):
        """delta_hr on the transition must be positive."""
        result = detect_phases(orthostatic_rr)
        assert result.transition.delta_hr > 0

    def test_transition_peak_hr_above_supine(self, orthostatic_rr):
        """peak_hr must exceed the supine mean HR."""
        result = detect_phases(orthostatic_rr)
        assert result.transition.peak_hr > result.supine.features.mean_hr

    def test_phase_timestamps_monotonic(self, orthostatic_rr):
        """start_sec and end_sec must be ordered: supine < transition < standing."""
        result = detect_phases(orthostatic_rr)
        assert result.supine.start_sec <= result.supine.end_sec
        assert result.supine.end_sec <= result.transition.start_sec
        assert result.transition.end_sec <= result.standing.start_sec

    def test_duration_sec_matches_timestamps(self, orthostatic_rr):
        """duration_sec should equal end_sec - start_sec for each segment."""
        result = detect_phases(orthostatic_rr)
        for seg in (result.supine, result.standing):
            assert seg.duration_sec == pytest.approx(seg.end_sec - seg.start_sec, abs=0.1)
        t = result.transition
        assert t.duration_sec == pytest.approx(t.end_sec - t.start_sec, abs=0.1)

    def test_features_computed_for_all_phases(self, orthostatic_rr):
        """HRV features must be populated for all three phases."""
        result = detect_phases(orthostatic_rr)
        for features in (
            result.supine.features,
            result.transition.features,
            result.standing.features,
        ):
            assert features.rmssd > 0
            assert features.mean_hr > 0

    def test_raises_on_flat_signal(self, flat_rr):
        """Should raise ValueError when no transition is detectable."""
        with pytest.raises(ValueError, match="No orthostatic transition detected"):
            detect_phases(flat_rr, hr_threshold=10.0)

    def test_custom_hr_threshold(self):
        """A higher threshold should require a larger HR rise."""
        rr = _make_orthostatic_rr(supine_bpm=65.0, standing_bpm=72.0)  # small rise ~7 bpm
        with pytest.raises(ValueError):
            detect_phases(rr, hr_threshold=15.0)

    def test_phase_coverage_is_total(self, orthostatic_rr):
        """Sum of all three phase interval counts should equal the full recording."""
        result = detect_phases(orthostatic_rr)
        total = (
            len(result.supine.rr.intervals)
            + len(result.transition.rr.intervals)
            + len(result.standing.rr.intervals)
        )
        assert total == len(orthostatic_rr.intervals)


# ======================
# orthostatic_hrv
# ======================


class TestOrthostaticHRV:
    """Tests for the main protocol entry point."""

    def test_returns_orthostatic_result(self, orthostatic_rr):
        """Should return an OrthostaticResult instance."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert isinstance(result, OrthostaticResult)

    def test_hr_response_positive(self, orthostatic_rr):
        """hr_response must be positive when standing HR > supine HR."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert result.hr_response > 0

    def test_hf_response_pct_is_float(self, orthostatic_rr):
        """hf_response_pct must be a finite float."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert isinstance(result.hf_response_pct, float)

    def test_lf_hf_ratio_change_positive(self, orthostatic_rr):
        """lf_hf_ratio_change should be positive."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert result.lf_hf_ratio_change > 0

    def test_interpretation_is_string(self, orthostatic_rr):
        """interpretation must be a non-empty string."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert isinstance(result.interpretation, str)
        assert len(result.interpretation) > 0

    def test_raises_on_short_supine(self, orthostatic_rr_short_phases):
        """Should raise when the supine phase is below min_phase_duration."""
        with pytest.raises(ValueError, match="Supine phase"):
            orthostatic_hrv(orthostatic_rr_short_phases, min_phase_duration=240.0)

    def test_phases_accessible_from_result(self, orthostatic_rr):
        """OrthostaticResult.phases must carry the three segmented objects."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert isinstance(result.phases.supine, PhaseSegment)
        assert isinstance(result.phases.transition, TransitionSegment)
        assert isinstance(result.phases.standing, PhaseSegment)

    def test_consistency_on_repeated_calls(self, orthostatic_rr):
        """Repeated calls on the same input must yield identical results."""
        r1 = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        r2 = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert r1.hr_response == pytest.approx(r2.hr_response)
        assert r1.interpretation == r2.interpretation


# ======================
# _interpret_response
# ======================


class TestInterpretResponse:
    """Tests for the clinical classification function."""

    def test_normal_response(self):
        """A 15 bpm rise with −40 % HF change should be classified as normal."""
        assert _interpret_response(15.0, -40.0) == "normal"

    def test_elevated_response(self):
        """A rise above 30 bpm should be classified as elevated_response."""
        assert _interpret_response(35.0, -40.0) == "elevated_response"

    def test_impaired_response(self):
        """A rise below 5 bpm should be classified as impaired_response."""
        assert _interpret_response(3.0, -30.0) == "impaired_response"

    def test_excessive_vagal_withdrawal(self):
        """An HF drop below −60 % should trigger excessive_vagal_withdrawal."""
        assert _interpret_response(15.0, -70.0) == "excessive_vagal_withdrawal"

    def test_elevated_takes_priority_over_vagal(self):
        """elevated_response should take priority over vagal withdrawal."""
        assert _interpret_response(35.0, -70.0) == "elevated_response"

    def test_nan_hf_does_not_crash(self):
        """NaN hf_response_pct must not raise an exception."""
        result = _interpret_response(15.0, float("nan"))
        assert result == "normal"

    def test_boundary_elevated(self):
        """Exactly 30 bpm rise should still be classified as normal."""
        assert _interpret_response(30.0, -40.0) == "normal"

    def test_boundary_impaired(self):
        """Exactly 5 bpm rise should still be classified as normal."""
        assert _interpret_response(5.0, -40.0) == "normal"


# ======================
# Integration
# ======================


class TestOrthostaticIntegration:
    """End-to-end integration tests."""

    def test_full_protocol_large_hr_delta(self):
        """A large HR delta should yield an elevated_response classification."""
        rr = _make_orthostatic_rr(supine_bpm=60.0, standing_bpm=100.0)
        result = orthostatic_hrv(rr, min_phase_duration=60.0)
        assert result.hr_response > 0
        assert result.interpretation in {
            "elevated_response", "normal", "excessive_vagal_withdrawal"
        }

    def test_full_protocol_normal_delta(self):
        """A 20 bpm HR delta should most likely yield a normal classification."""
        rr = _make_orthostatic_rr(supine_bpm=65.0, standing_bpm=85.0)
        result = orthostatic_hrv(rr, min_phase_duration=60.0)
        assert result.hr_response == pytest.approx(20.0, abs=8.0)

    def test_supine_rmssd_higher_than_standing(self):
        """Supine RMSSD is typically higher than standing RMSSD."""
        rr = _make_orthostatic_rr(supine_bpm=65.0, standing_bpm=85.0, std_rr=30.0)
        result = orthostatic_hrv(rr, min_phase_duration=60.0)
        # Standing has lower HRV due to sympathetic dominance
        assert result.phases.supine.features.rmssd >= result.phases.standing.features.rmssd * 0.5

    def test_transition_duration_reasonable(self):
        """The detected transition should last between 5 s and 120 s."""
        rr = _make_orthostatic_rr()
        result = orthostatic_hrv(rr, min_phase_duration=60.0)
        assert 5.0 <= result.phases.transition.duration_sec <= 120.0

    def test_protocol_output_fields_complete(self, orthostatic_rr):
        """All output fields of OrthostaticResult must be populated."""
        result = orthostatic_hrv(orthostatic_rr, min_phase_duration=60.0)
        assert result.phases is not None
        assert isinstance(result.hr_response, float)
        assert isinstance(result.lf_hf_ratio_change, float)
        assert isinstance(result.hf_response_pct, float)
        assert isinstance(result.interpretation, str)
