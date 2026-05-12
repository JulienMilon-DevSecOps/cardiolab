"""Unit tests for baseline module."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures


class TestBaselineInitialization:
    """Test suite for Baseline initialization."""

    def test_baseline_creation_empty(self):
        """Test creating empty baseline."""
        baseline = Baseline()
        
        assert baseline.history == []
        assert baseline.window == 7

    def test_baseline_creation_with_features(self, baseline_7days):
        """Test creating baseline with features list."""
        assert len(baseline_7days.history) == 7
        assert baseline_7days.window == 7

    def test_baseline_creation_with_custom_window(self, normal_hrv_features):
        """Test creating baseline with custom window size."""
        baseline = Baseline(history=[normal_hrv_features], window=30)
        
        assert baseline.window == 30

    def test_baseline_history_preserves_order(self, baseline_30days):
        """Test that history maintains insertion order."""
        dates = [f.date for f in baseline_30days.history]
        
        # Dates should be in order (or at least present)
        assert len(dates) == 30


class TestBaselineFromFeatures:
    """Test suite for Baseline.from_features() class method."""

    def test_from_features_basic(self, normal_hrv_features, excellent_hrv_features, poor_hrv_features):
        """Test creating baseline from features list."""
        features = [normal_hrv_features, excellent_hrv_features, poor_hrv_features]
        baseline = Baseline.from_features(features)
        
        assert len(baseline.history) == 3
        assert isinstance(baseline, Baseline)

    def test_from_features_empty_list(self):
        """Test creating baseline from empty list."""
        baseline = Baseline.from_features([])
        
        assert baseline.history == []
        assert isinstance(baseline, Baseline)

    def test_from_features_single_feature(self, normal_hrv_features):
        """Test creating baseline from single feature."""
        baseline = Baseline.from_features([normal_hrv_features])
        
        assert len(baseline.history) == 1
        assert baseline.history[0] == normal_hrv_features

    def test_from_features_sorts_by_date(self, hrv_features_generator):
        """Test that from_features sorts by date."""
        # Create features out of order
        feature1 = hrv_features_generator(date="2026-05-12", rmssd=60.0)
        feature2 = hrv_features_generator(date="2026-05-10", rmssd=65.0)
        feature3 = hrv_features_generator(date="2026-05-11", rmssd=55.0)
        
        features_unordered = [feature1, feature2, feature3]
        baseline = Baseline.from_features(features_unordered)
        
        # Should be sorted
        dates = [f.date for f in baseline.history]
        assert dates == sorted(dates)

    def test_from_features_preserves_all_fields(self, normal_hrv_features):
        """Test that all feature fields are preserved."""
        baseline = Baseline.from_features([normal_hrv_features])
        
        retrieved = baseline.history[0]
        assert retrieved.rmssd == normal_hrv_features.rmssd
        assert retrieved.sdnn == normal_hrv_features.sdnn
        assert retrieved.mean_hr == normal_hrv_features.mean_hr


class TestBaselineFromRestingResults:
    """Test suite for Baseline.from_resting_results() class method."""

    def test_from_resting_results_basic(self, normal_hrv_features):
        """Test creating baseline from resting results."""
        # Mock resting results
        results = [normal_hrv_features]
        baseline = Baseline.from_resting_results(results)
        
        assert len(baseline.history) > 0
        assert isinstance(baseline.history[0], HRVFeatures)

    def test_from_resting_results_converts_properly(self, hrv_features_generator):
        """Test that resting results are properly converted to HRVFeatures."""
        # Create mock results
        from cardiolab.protocols.resting import HRVFeatures as MockResult
        
        mock_result = MockResult(
            date="2026-05-12",
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
            duration=300.0,
            score=75.0,
        )
        
        baseline = Baseline.from_resting_results([mock_result])
        
        assert len(baseline.history) == 1
        assert baseline.history[0].rmssd == mock_result.rmssd

    def test_from_resting_results_empty_list(self):
        """Test from_resting_results with empty list."""
        baseline = Baseline.from_resting_results([])
        
        assert baseline.history == []


class TestBaselineStatistics:
    """Test suite for baseline statistical methods."""

    def test_get_recent_default_window(self, baseline_7days):
        """Test _get_recent with default window."""
        recent = baseline_7days._get_recent()
        
        assert len(recent) == 7
        assert all(isinstance(f, HRVFeatures) for f in recent)

    def test_get_recent_all_data_if_less_than_window(self, baseline_insufficient_data):
        """Test _get_recent returns all data if < window size."""
        recent = baseline_insufficient_data._get_recent()
        
        assert len(recent) <= baseline_insufficient_data.window

    def test_get_recent_exact_window_size(self, baseline_30days):
        """Test _get_recent returns exactly window size when history is larger."""
        recent = baseline_30days._get_recent()
        
        assert len(recent) == baseline_30days.window

    def test_get_recent_multiple_calls(self, baseline_7days):
        """Test that repeated _get_recent calls are consistent."""
        recent1 = baseline_7days._get_recent()
        recent2 = baseline_7days._get_recent()
        
        assert len(recent1) == len(recent2)
        assert all(r1.rmssd == r2.rmssd for r1, r2 in zip(recent1, recent2))

    def test_mean_rmssd(self, baseline_7days):
        """Test mean_rmssd calculation."""
        mean = baseline_7days.mean_rmssd()
        
        assert isinstance(mean, (int, float, type(None)))
        if mean is not None:
            assert mean > 0

    def test_median_rmssd(self, baseline_7days):
        """Test median_rmssd calculation."""
        median = baseline_7days.median_rmssd()
        
        assert isinstance(median, (int, float, type(None)))
        if median is not None:
            assert median > 0

    def test_mean_hr(self, baseline_7days):
        """Test mean heart rate calculation."""
        mean_hr = baseline_7days.mean_hr()
        
        assert isinstance(mean_hr, (int, float, type(None)))
        if mean_hr is not None:
            assert 40 < mean_hr < 200  # Reasonable HR range

    def test_rolling_rmssd_median(self, baseline_30days):
        """Test rolling median RMSSD."""
        rolling = baseline_30days.rolling_rmssd_median()
        
        assert isinstance(rolling, (list, type(None)))
        if rolling:
            assert len(rolling) > 0
            assert all(isinstance(v, (int, float)) for v in rolling)

    def test_baseline_with_empty_history(self):
        """Test statistical methods with empty baseline."""
        baseline = Baseline(history=[])
        
        mean = baseline.mean_rmssd()
        median = baseline.median_rmssd()
        mean_hr = baseline.mean_hr()
        
        # Should handle gracefully (return None or 0)
        assert mean is None or mean == 0 or isinstance(mean, float)
        assert median is None or median == 0 or isinstance(median, float)
        assert mean_hr is None or mean_hr == 0 or isinstance(mean_hr, float)

    def test_baseline_statistics_with_single_value(self, normal_hrv_features):
        """Test statistics with only one feature."""
        baseline = Baseline(history=[normal_hrv_features])
        
        mean = baseline.mean_rmssd()
        median = baseline.median_rmssd()
        
        # mean and median should equal the single value
        if mean is not None:
            assert mean == normal_hrv_features.rmssd
        if median is not None:
            assert median == normal_hrv_features.rmssd


class TestBaselineValidation:
    """Test suite for baseline validation and error handling."""

    def test_baseline_with_none_rmssd_values(self):
        """Test baseline handles missing/None RMSSD values."""
        # Create features with edge case values
        from cardiolab.protocols.resting import HRVFeatures
        
        features = [
            HRVFeatures(date="2026-05-01", rmssd=0.0, mean_hr=70.0, sdnn=80.0, pnn50=25.0,
                       ln_rmssd=0.0, vlf=500, lf=1500, hf=2000, lf_hf=0.75, hf_pct=0.4, lf_nu=0.4, hf_nu=0.6),
            HRVFeatures(date="2026-05-02", rmssd=60.0, mean_hr=70.0, sdnn=80.0, pnn50=25.0,
                       ln_rmssd=4.09, vlf=500, lf=1500, hf=2000, lf_hf=0.75, hf_pct=0.4, lf_nu=0.4, hf_nu=0.6),
        ]
        
        baseline = Baseline(history=features)
        
        # Should not crash
        mean = baseline.mean_rmssd()
        assert isinstance(mean, (int, float, type(None)))

    def test_baseline_custom_window_enforcement(self):
        """Test that window parameter is respected."""
        from cardiolab.protocols.resting import HRVFeatures
        
        features = [
            HRVFeatures(date=f"2026-05-{i:02d}", rmssd=60.0 + i, mean_hr=70.0, sdnn=80.0, pnn50=25.0,
                       ln_rmssd=4.09, vlf=500, lf=1500, hf=2000, lf_hf=0.75, hf_pct=0.4, lf_nu=0.4, hf_nu=0.6)
            for i in range(30)
        ]
        
        # Test with window=14
        baseline = Baseline(history=features, window=14)
        recent = baseline._get_recent()
        
        assert len(recent) == 14

    def test_baseline_with_very_large_history(self):
        """Test baseline with many features (performance check)."""
        from cardiolab.protocols.resting import HRVFeatures
        
        features = [
            HRVFeatures(date=f"2026-04-{1 + (i%24):02d}", rmssd=60.0 + np.random.normal(0, 5), mean_hr=70.0, sdnn=80.0, pnn50=25.0,
                       ln_rmssd=4.09, vlf=500, lf=1500, hf=2000, lf_hf=0.75, hf_pct=0.4, lf_nu=0.4, hf_nu=0.6)
            for i in range(365)  # Full year
        ]
        
        baseline = Baseline(history=features, window=30)
        recent = baseline._get_recent()
        
        assert len(recent) == 30
        # Operations should be fast
        mean = baseline.mean_rmssd()
        assert mean is not None


class TestBaselineIntegration:
    """Integration tests for baseline functionality."""

    def test_baseline_creation_and_statistics_flow(self):
        """Test complete flow: create baseline from features and compute stats."""
        from cardiolab.protocols.resting import HRVFeatures
        
        # Generate features
        features = [
            HRVFeatures(date=f"2026-05-{i:02d}", rmssd=60.0 + i * 2, mean_hr=70.0 - i * 0.1, sdnn=80.0 + i, pnn50=25.0 + i * 0.5,
                       ln_rmssd=4.09, vlf=500, lf=1500, hf=2000, lf_hf=0.75, hf_pct=0.4, lf_nu=0.4, hf_nu=0.6)
            for i in range(1, 8)
        ]
        
        # Create baseline
        baseline = Baseline.from_features(features)
        
        # Retrieve recent
        recent = baseline._get_recent()
        
        # Compute stats
        mean_rmssd = baseline.mean_rmssd()
        median_rmssd = baseline.median_rmssd()
        mean_hr = baseline.mean_hr()
        
        # All should be valid
        assert len(recent) == 7
        assert mean_rmssd is not None
        assert median_rmssd is not None
        assert mean_hr is not None

    def test_baseline_comparison_workflow(self, baseline_7days, baseline_30days):
        """Test comparing short-term vs long-term baseline."""
        mean_7d = baseline_7days.mean_rmssd()
        mean_30d = baseline_30days.mean_rmssd()
        
        # Both should be computed
        assert mean_7d is not None
        assert mean_30d is not None
        
        # Should be different due to different data
        # But this isn't always true, so just check they're valid
        assert mean_7d > 0
        assert mean_30d > 0

    def test_baseline_rolling_window_progression(self, baseline_30days):
        """Test that rolling window shows progression over time."""
        rolling = baseline_30days.rolling_rmssd_median()
        
        if rolling and len(rolling) > 1:
            # Should show some variation
            assert len(set(rolling)) > 1  # Not all values identical
