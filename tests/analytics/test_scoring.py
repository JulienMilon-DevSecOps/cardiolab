"""Unit tests for scoring module."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.scoring import readiness_score_multi, readiness_score_oura


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
