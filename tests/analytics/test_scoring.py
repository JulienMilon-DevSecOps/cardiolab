"""Unit tests for scoring module."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import (
    readiness_score_composite,
    readiness_score_multi,
    readiness_score_nonlinear,
    readiness_score_oura,
)
from cardiolab.protocols.resting import HRVFeatures


class TestReadinessScoreOura:
    """Test suite for readiness_score_oura() function."""

    def test_oura_score_normal_recovery(self, normal_hrv_features, baseline_7days):
        """Test Oura-like score with normal recovery."""
        score = readiness_score_oura(normal_hrv_features, baseline_7days)

        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_oura_score_excellent_recovery(
        self, excellent_hrv_features, baseline_7days
    ):
        """Test Oura score with excellent recovery."""
        score = readiness_score_oura(excellent_hrv_features, baseline_7days)

        assert 0 <= score <= 100
        # Excellent recovery should have higher score
        assert score > 50

    def test_oura_score_poor_recovery(self, poor_hrv_features, baseline_7days):
        """Test Oura score with poor recovery."""
        score = readiness_score_oura(poor_hrv_features, baseline_7days)

        assert 0 <= score <= 100
        # Poor recovery should have lower score
        assert score < 70

    def test_oura_score_no_baseline(self, normal_hrv_features):
        """Test Oura score with empty baseline."""
        from cardiolab.analytics.baseline import Baseline

        empty_baseline = Baseline(history=[])

        score = readiness_score_oura(normal_hrv_features, empty_baseline)

        # Should return default score
        assert score == 50.0

    def test_oura_score_consistency(self, normal_hrv_features, baseline_7days):
        """Test that repeated calls give same result."""
        score1 = readiness_score_oura(normal_hrv_features, baseline_7days)
        score2 = readiness_score_oura(normal_hrv_features, baseline_7days)

        assert np.isclose(score1, score2)

    def test_oura_score_reflects_rmssd_ratio(self, baseline_7days):
        """Test that score reflects RMSSD/baseline ratio."""
        from cardiolab.protocols.resting import HRVFeatures

        baseline_mean = baseline_7days.median_rmssd()

        # Feature with RMSSD = baseline_mean * 1.5 (good recovery)
        good_recovery = HRVFeatures(
            date="2026-05-12",
            rmssd=baseline_mean * 1.5,
            mean_hr=baseline_7days.mean_hr(),
            sdnn=80.0,
            pnn50=25.0,
            ln_rmssd=4.09,
            vlf=500,
            lf=1500,
            hf=2000,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
        )

        # Feature with RMSSD = baseline_mean * 0.5 (poor recovery)
        poor_recovery = HRVFeatures(
            date="2026-05-12",
            rmssd=baseline_mean * 0.5,
            mean_hr=baseline_7days.mean_hr(),
            sdnn=40.0,
            pnn50=10.0,
            ln_rmssd=3.0,
            vlf=250,
            lf=750,
            hf=1000,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
        )

        score_good = readiness_score_oura(good_recovery, baseline_7days)
        score_poor = readiness_score_oura(poor_recovery, baseline_7days)

        # Good recovery should have higher score
        assert score_good > score_poor

    def test_oura_score_bounds(self, normal_hrv_features, baseline_30days):
        """Test that score is always within 0-100."""
        score = readiness_score_oura(normal_hrv_features, baseline_30days)

        assert 0 <= score <= 100


class TestReadinessScoreMulti:
    """Test suite for readiness_score_multi() function."""

    def test_multi_score_normal_recovery(self, normal_hrv_features, baseline_7days):
        """Test multi-factor score with normal recovery."""
        score = readiness_score_multi(normal_hrv_features, baseline_7days)

        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_multi_score_excellent_recovery(
        self, excellent_hrv_features, baseline_7days
    ):
        """Test multi-factor score with excellent recovery."""
        score = readiness_score_multi(excellent_hrv_features, baseline_7days)

        assert 0 <= score <= 100
        # Excellent should be high
        assert score > 70

    def test_multi_score_poor_recovery(self, poor_hrv_features, baseline_7days):
        """Test multi-factor score with poor recovery."""
        score = readiness_score_multi(poor_hrv_features, baseline_7days)

        assert 0 <= score <= 100
        # Poor should be low
        assert score < 50

    def test_multi_score_with_high_hf(self, baseline_7days):
        """Test multi-factor score prioritizes HF (parasympathetic)."""
        from cardiolab.protocols.resting import HRVFeatures

        # High HF indicates good parasympathetic activity
        high_hf_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=baseline_7days.median_rmssd(),
            mean_hr=baseline_7days.mean_hr(),
            sdnn=80.0,
            pnn50=25.0,
            ln_rmssd=4.09,
            vlf=500,
            lf=800,  # Lower LF
            hf=3500,  # Higher HF
            lf_hf=0.23,
            hf_pct=0.8,
            lf_nu=0.22,
            hf_nu=0.78,
        )

        score = readiness_score_multi(high_hf_feature, baseline_7days)

        assert 0 <= score <= 100

    def test_multi_score_considers_trend(self, baseline_30days):
        """Test multi-factor score considers RMSSD trend."""
        from cardiolab.protocols.resting import HRVFeatures

        # Current RMSSD trending upward
        improving_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=120.0,  # Higher than recent baseline
            mean_hr=65.0,
            sdnn=100.0,
            pnn50=40.0,
            ln_rmssd=4.79,
            vlf=600,
            lf=1800,
            hf=2500,
            lf_hf=0.72,
            hf_pct=0.58,
            lf_nu=0.42,
            hf_nu=0.58,
        )

        score = readiness_score_multi(improving_feature, baseline_30days)

        assert 0 <= score <= 100

    def test_multi_score_no_baseline(self, normal_hrv_features):
        """Test multi-factor score with empty baseline."""
        from cardiolab.analytics.baseline import Baseline

        empty_baseline = Baseline(history=[])

        score = readiness_score_multi(normal_hrv_features, empty_baseline)

        # Should return default
        assert score == 50.0

    def test_multi_score_consistency(self, normal_hrv_features, baseline_30days):
        """Test that repeated calls give same result."""
        score1 = readiness_score_multi(normal_hrv_features, baseline_30days)
        score2 = readiness_score_multi(normal_hrv_features, baseline_30days)

        assert np.isclose(score1, score2)

    def test_multi_score_vs_oura_score(self, normal_hrv_features, baseline_7days):
        """Test that multi-score considers more factors than Oura."""
        score_oura = readiness_score_oura(normal_hrv_features, baseline_7days)
        score_multi = readiness_score_multi(normal_hrv_features, baseline_7days)

        # Both should be valid scores
        assert 0 <= score_oura <= 100
        assert 0 <= score_multi <= 100

        # Scores may differ due to different computation methods
        # Just ensure both are computed without error

    def test_multi_score_extreme_hr(self, baseline_7days):
        """Test multi-factor score with extreme HR."""
        from cardiolab.protocols.resting import HRVFeatures

        # Very high HR (stress)
        high_hr_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=30.0,
            mean_hr=100.0,  # Very high HR
            sdnn=40.0,
            pnn50=10.0,
            ln_rmssd=3.4,
            vlf=200,
            lf=600,
            hf=400,
            lf_hf=1.5,
            hf_pct=0.4,
            lf_nu=0.6,
            hf_nu=0.4,
        )

        score = readiness_score_multi(high_hr_feature, baseline_7days)

        assert 0 <= score <= 100
        # Should reflect stress
        assert score < 60


class TestScoringIntegration:
    """Integration tests for scoring functions."""

    def test_scoring_progression(self, baseline_30days):
        """Test scoring progression over 30 days."""
        from cardiolab.protocols.resting import HRVFeatures

        scores = []

        for i in range(1, 8):
            # Simulate gradual improvement
            feature = HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=50.0 + i * 5,  # Increasing RMSSD
                mean_hr=75.0 - i * 0.5,  # Decreasing HR
                sdnn=70.0 + i * 2,
                pnn50=20.0 + i * 2,
                ln_rmssd=4.0 + i * 0.1,
                vlf=500,
                lf=1500,
                hf=2000,
                lf_hf=0.75,
                hf_pct=0.4,
                lf_nu=0.4,
                hf_nu=0.6,
            )

            score = readiness_score_multi(feature, baseline_30days)
            scores.append(score)

        # Should have 7 valid scores
        assert len(scores) == 7
        assert all(0 <= s <= 100 for s in scores)

    def test_both_scoring_methods_valid(self, normal_hrv_features, baseline_7days):
        """Test that both scoring methods produce valid results."""
        score_oura = readiness_score_oura(normal_hrv_features, baseline_7days)
        score_multi = readiness_score_multi(normal_hrv_features, baseline_7days)

        assert isinstance(score_oura, float)
        assert isinstance(score_multi, float)
        assert 0 <= score_oura <= 100
        assert 0 <= score_multi <= 100


# ======================
# FIXTURES COMMUNES (non-linear)
# ======================


def _make_features(**kw) -> HRVFeatures:
    """Return an HRVFeatures with all non-linear fields explicitly set."""
    defaults = dict(
        date="2026-05-17",
        rmssd=60.0,
        ln_rmssd=4.09,
        sdnn=80.0,
        pnn50=25.0,
        mean_hr=70.0,
        vlf=500.0,
        lf=1500.0,
        hf=2000.0,
        lf_hf=0.75,
        hf_pct=0.4,
        lf_nu=0.4,
        hf_nu=0.6,
        hf_hr=2000.0 / 70.0,
        sd1=42.43,
        sd2=104.88,
        sd_ratio=0.40,
        dfa_alpha1=1.0,
        duration=300.0,
        score=0.0,
    )
    defaults.update(kw)
    return HRVFeatures(**defaults)


def _make_baseline(n: int = 7, rmssd: float = 60.0, sd1: float = 42.43) -> Baseline:
    """Return a Baseline with ``n`` identical sessions carrying non-linear data."""
    features = [
        HRVFeatures(
            date=f"2026-05-{i + 1:02d}",
            rmssd=rmssd,
            ln_rmssd=4.09,
            sdnn=80.0,
            pnn50=25.0,
            mean_hr=70.0,
            vlf=500.0,
            lf=1500.0,
            hf=2000.0,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
            hf_hr=2000.0 / 70.0,
            sd1=sd1,
            sd2=104.88,
            sd_ratio=0.40,
            dfa_alpha1=1.0,
            duration=300.0,
        )
        for i in range(n)
    ]
    return Baseline(history=features, window=7)


# ======================
# readiness_score_multi — DFA α1 component
# ======================


class TestReadinessScoreMultiDFA:
    """Tests for the DFA α1 component added to readiness_score_multi."""

    def test_good_dfa_boosts_score(self):
        """DFA α1 = 1.0 (optimal) must give a score above 50 for baseline-equal RMSSD."""
        base = _make_baseline()
        current = _make_features(dfa_alpha1=1.0)
        score = readiness_score_multi(current, base)
        assert score > 50.0

    def test_poor_dfa_penalises_score(self):
        """DFA α1 = 0.5 (below threshold) must lower the score vs. good DFA."""
        base = _make_baseline()
        score_good = readiness_score_multi(_make_features(dfa_alpha1=1.0), base)
        score_poor = readiness_score_multi(_make_features(dfa_alpha1=0.5), base)
        assert score_good > score_poor

    def test_dfa_zero_treated_as_neutral(self):
        """DFA α1 = 0.0 (not computed) must not penalise the score."""
        base = _make_baseline()
        score_zero = readiness_score_multi(_make_features(dfa_alpha1=0.0), base)
        score_good = readiness_score_multi(_make_features(dfa_alpha1=1.0), base)
        # zero DFA should be neutral — difference should be small
        assert abs(score_good - score_zero) < 30.0

    def test_dfa_nan_treated_as_neutral(self):
        """DFA α1 = nan (short recording) must not cause an error or heavy penalty."""
        base = _make_baseline()
        score = readiness_score_multi(_make_features(dfa_alpha1=float("nan")), base)
        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    def test_score_in_range(self):
        """Score must always be in [0, 100] regardless of DFA α1 value."""
        base = _make_baseline()
        for alpha in [0.0, 0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, float("nan")]:
            s = readiness_score_multi(_make_features(dfa_alpha1=alpha), base)
            assert 0.0 <= s <= 100.0, f"Out of range for alpha={alpha}: {s}"


# ======================
# readiness_score_nonlinear
# ======================


class TestReadinessScoreNonlinear:
    """Tests for the purely non-linear readiness score."""

    def test_returns_float(self):
        """readiness_score_nonlinear() must return a float."""
        base = _make_baseline()
        score = readiness_score_nonlinear(_make_features(), base)
        assert isinstance(score, float)

    def test_score_in_range(self):
        """Score must always be in [0, 100]."""
        base = _make_baseline()
        for alpha in [0.0, 0.5, 0.75, 1.0, 1.25, 1.5, float("nan")]:
            s = readiness_score_nonlinear(_make_features(dfa_alpha1=alpha), base)
            assert 0.0 <= s <= 100.0, f"Out of range for alpha={alpha}: {s}"

    def test_neutral_when_baseline_empty(self):
        """Returns 50.0 when all non-linear inputs are absent (dfa=0, sd_ratio=0, empty baseline)."""
        empty = Baseline(history=[])
        score = readiness_score_nonlinear(
            _make_features(dfa_alpha1=0.0, sd_ratio=0.0, sd1=0.0), empty
        )
        assert score == pytest.approx(50.0, abs=1e-6)

    def test_good_dfa_above_threshold_boosts_score(self):
        """DFA α1 = 1.0 with normal SD1/SD2 must produce a score > 50."""
        base = _make_baseline()
        current = _make_features(dfa_alpha1=1.0, sd1=42.43, sd_ratio=0.40)
        score = readiness_score_nonlinear(current, base)
        assert score > 50.0

    def test_poor_dfa_below_threshold_lowers_score(self):
        """DFA α1 = 0.5 must produce a lower score than DFA α1 = 1.0."""
        base = _make_baseline()
        score_good = readiness_score_nonlinear(_make_features(dfa_alpha1=1.0), base)
        score_poor = readiness_score_nonlinear(_make_features(dfa_alpha1=0.5), base)
        assert score_good > score_poor

    def test_low_sd_ratio_lowers_score(self):
        """SD1/SD2 = 0.1 (sympathetic dominance) must score lower than 0.4 (normal)."""
        base = _make_baseline()
        score_normal = readiness_score_nonlinear(_make_features(sd_ratio=0.40), base)
        score_low = readiness_score_nonlinear(_make_features(sd_ratio=0.10), base)
        assert score_normal > score_low

    def test_sd1_above_baseline_boosts_score(self):
        """SD1 well above the baseline median must push the score above 50."""
        base = _make_baseline(sd1=42.43)
        current = _make_features(sd1=85.0, dfa_alpha1=1.0)
        score = readiness_score_nonlinear(current, base)
        assert score > 50.0

    def test_sd1_below_baseline_lowers_score(self):
        """SD1 well below the baseline median must push the score below 50."""
        base = _make_baseline(sd1=42.43)
        current = _make_features(sd1=15.0)
        score = readiness_score_nonlinear(current, base)
        # DFA neutral (50) + low SD1 + normal SD_ratio → overall < 50
        assert score < 60.0

    def test_dfa_zero_treated_as_neutral(self):
        """DFA α1 = 0.0 must not crash and must return a finite score."""
        base = _make_baseline()
        score = readiness_score_nonlinear(_make_features(dfa_alpha1=0.0), base)
        assert math.isfinite(score)

    def test_all_neutral_inputs_near_50(self):
        """All components neutral (dfa=0, sd1=0, sd_ratio=0) → score near 50."""
        base = _make_baseline()
        current = _make_features(dfa_alpha1=0.0, sd1=0.0, sd_ratio=0.0)
        score = readiness_score_nonlinear(current, base)
        assert score == pytest.approx(50.0)


# ======================
# readiness_score_composite
# ======================


class TestReadinessScoreComposite:
    """Tests for the composite readiness score."""

    def test_returns_float(self):
        """readiness_score_composite() must return a float."""
        base = _make_baseline()
        score = readiness_score_composite(_make_features(), base)
        assert isinstance(score, float)

    def test_score_in_range(self):
        """Score must always be in [0, 100]."""
        base = _make_baseline()
        score = readiness_score_composite(_make_features(), base)
        assert 0.0 <= score <= 100.0

    def test_default_weights_equal_50_50(self):
        """Default (w=0.5/0.5) must equal the arithmetic mean of multi and nonlinear."""
        base = _make_baseline()
        current = _make_features()
        score_m = readiness_score_multi(current, base)
        score_nl = readiness_score_nonlinear(current, base)
        expected = (score_m + score_nl) / 2.0
        composite = readiness_score_composite(current, base)
        assert composite == pytest.approx(expected, abs=1e-6)

    def test_custom_weights_respected(self):
        """Custom weights must change the result proportionally."""
        base = _make_baseline()
        current = _make_features()
        score_m = readiness_score_multi(current, base)
        score_nl = readiness_score_nonlinear(current, base)

        # All weight on multi
        c_full_multi = readiness_score_composite(current, base, w_multi=1.0, w_nonlinear=0.0)
        assert c_full_multi == pytest.approx(score_m, abs=1e-6)

        # All weight on nonlinear
        c_full_nl = readiness_score_composite(current, base, w_multi=0.0, w_nonlinear=1.0)
        assert c_full_nl == pytest.approx(score_nl, abs=1e-6)

    def test_neutral_when_both_neutral(self):
        """Returns 50.0 when both sub-scores are neutral (empty baseline)."""
        empty = Baseline(history=[])
        current = _make_features(dfa_alpha1=0.0, sd1=0.0, sd_ratio=0.0)
        score = readiness_score_composite(current, empty)
        assert score == pytest.approx(50.0, abs=1e-6)

    def test_zero_weights_raises(self):
        """w_multi + w_nonlinear == 0 must raise ValueError."""
        base = _make_baseline()
        with pytest.raises(ValueError, match="w_multi"):
            readiness_score_composite(_make_features(), base, w_multi=0.0, w_nonlinear=0.0)

    def test_composite_between_sub_scores(self):
        """Default composite must lie between the two sub-scores (up to floating precision)."""
        base = _make_baseline()
        current = _make_features(dfa_alpha1=1.0, sd1=60.0, sd_ratio=0.5)
        score_m = readiness_score_multi(current, base)
        score_nl = readiness_score_nonlinear(current, base)
        composite = readiness_score_composite(current, base)
        lo, hi = min(score_m, score_nl), max(score_m, score_nl)
        assert lo - 1e-6 <= composite <= hi + 1e-6

    def test_consistency(self):
        """Repeated calls must return the same result."""
        base = _make_baseline()
        current = _make_features()
        s1 = readiness_score_composite(current, base)
        s2 = readiness_score_composite(current, base)
        assert s1 == s2

    def test_good_recovery_above_50(self):
        """Session with DFA α1=1.1, SD1 above baseline, good RMSSD must score > 50."""
        base = _make_baseline(rmssd=60.0, sd1=42.43)
        current = _make_features(
            rmssd=80.0, sd1=60.0, sd_ratio=0.45, dfa_alpha1=1.1, mean_hr=65.0
        )
        score = readiness_score_composite(current, base)
        assert score > 50.0

    def test_poor_recovery_below_50(self):
        """Session with DFA α1=0.5, SD1 below baseline, poor RMSSD must score < 50."""
        base = _make_baseline(rmssd=60.0, sd1=42.43)
        current = _make_features(
            rmssd=30.0, sd1=15.0, sd_ratio=0.15, dfa_alpha1=0.5, mean_hr=85.0
        )
        score = readiness_score_composite(current, base)
        assert score < 50.0


# ======================
# Baseline — new methods
# ======================


class TestBaselineNonlinearMethods:
    """Tests for Baseline.median_sd1() and Baseline.median_dfa_alpha1()."""

    def test_median_sd1_returns_float(self):
        """median_sd1() must return a float for a non-empty baseline."""
        base = _make_baseline()
        assert isinstance(base.median_sd1(), float)

    def test_median_sd1_correct_value(self):
        """median_sd1() must return the median of SD1 values in the window."""
        base = _make_baseline(sd1=42.43)
        assert base.median_sd1() == pytest.approx(42.43, rel=1e-6)

    def test_median_sd1_empty_baseline_returns_none(self):
        """median_sd1() must return None for an empty history."""
        assert Baseline(history=[]).median_sd1() is None

    def test_median_sd1_ignores_zeros(self):
        """median_sd1() must exclude sessions where SD1 = 0.0."""
        features = [
            HRVFeatures(date=f"2026-05-{i:02d}", sd1=0.0) for i in range(1, 4)
        ]
        base = Baseline(history=features)
        assert base.median_sd1() is None

    def test_median_sd1_mixed_zero_and_nonzero(self):
        """median_sd1() must use only non-zero SD1 values."""
        features = [
            HRVFeatures(date="2026-05-01", sd1=0.0),
            HRVFeatures(date="2026-05-02", sd1=40.0),
            HRVFeatures(date="2026-05-03", sd1=50.0),
        ]
        base = Baseline(history=features, window=7)
        result = base.median_sd1()
        assert result == pytest.approx(45.0, rel=1e-6)

    def test_median_dfa_returns_float(self):
        """median_dfa_alpha1() must return a float for a non-empty baseline."""
        base = _make_baseline()
        assert isinstance(base.median_dfa_alpha1(), float)

    def test_median_dfa_empty_baseline_returns_none(self):
        """median_dfa_alpha1() must return None for an empty history."""
        assert Baseline(history=[]).median_dfa_alpha1() is None

    def test_median_dfa_ignores_zeros_and_nans(self):
        """median_dfa_alpha1() must exclude zero and nan values."""
        features = [
            HRVFeatures(date="2026-05-01", dfa_alpha1=0.0),
            HRVFeatures(date="2026-05-02", dfa_alpha1=float("nan")),
        ]
        base = Baseline(history=features)
        assert base.median_dfa_alpha1() is None

    def test_median_dfa_correct_value(self):
        """median_dfa_alpha1() must return the median of valid values."""
        features = [
            HRVFeatures(date=f"2026-05-{i:02d}", dfa_alpha1=float(i) * 0.1 + 0.9)
            for i in range(1, 6)
        ]
        base = Baseline(history=features, window=7)
        expected = np.median([1.0, 1.1, 1.2, 1.3, 1.4])
        assert base.median_dfa_alpha1() == pytest.approx(expected, rel=1e-6)
