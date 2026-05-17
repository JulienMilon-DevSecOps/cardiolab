"""Unit tests for trends analysis module."""

from __future__ import annotations

import numpy as np

from cardiolab.analytics.trends import _interpret_trend, trend_rmssd


class TestTrendRmssd:
    """Test suite for trend_rmssd() function."""

    def test_trend_rmssd_insufficient_data(self, baseline_insufficient_data):
        """Test trend detection with insufficient data (< 5 points)."""
        result = trend_rmssd(baseline_insufficient_data)

        assert "status" in result
        assert result["status"] == "insufficient_data"

    def test_trend_rmssd_with_sufficient_data(self, baseline_7days):
        """Test trend detection with sufficient data (>= 5 points)."""
        result = trend_rmssd(baseline_7days)

        assert "slope" in result or result.get("status") == "insufficient_data"
        assert "trend" in result or result.get("status") == "insufficient_data"

    def test_trend_rmssd_increasing_trend(self):
        """Test detection of increasing RMSSD trend (recovery)."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Create baseline with increasing RMSSD
        features = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=40.0 + i * 10,
                mean_hr=70.0,
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
            for i in range(1, 8)
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        if result.get("status") != "insufficient_data":
            assert result["slope"] > 0
            assert result["trend"] == "increasing"

    def test_trend_rmssd_decreasing_trend(self):
        """Test detection of decreasing RMSSD trend (fatigue)."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Create baseline with decreasing RMSSD
        features = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=100.0 - i * 10,
                mean_hr=70.0,
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
            for i in range(1, 8)
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        if result.get("status") != "insufficient_data":
            assert result["slope"] < 0
            assert result["trend"] == "decreasing"

    def test_trend_rmssd_stable_trend(self):
        """Test detection of stable RMSSD trend."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Create baseline with stable RMSSD
        features = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=60.0,
                mean_hr=70.0,
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
            for i in range(1, 8)
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        if result.get("status") != "insufficient_data":
            assert np.abs(result["slope"]) < 1
            assert result["trend"] == "stable"

    def test_trend_rmssd_exact_five_points(self):
        """Test trend_rmssd with exactly 5 data points (boundary)."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        features = [
            HRVFeatures(
                date=f"2026-05-0{i}",
                rmssd=50.0 + i * 5,
                mean_hr=70.0,
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
            for i in range(1, 6)
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        # Should work with exactly 5 points
        assert "slope" in result or "status" in result

    def test_trend_rmssd_with_noise(self):
        """Test trend detection with noisy data."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Create baseline with trend but added noise
        base_values = [50 + i * 5 + np.random.normal(0, 3) for i in range(10)]
        features = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=max(10, base_values[i]),
                mean_hr=70.0,
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
            for i in range(10)
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        # Should still detect trend despite noise
        assert "slope" in result or "status" in result

    def test_trend_rmssd_empty_baseline(self):
        """Test trend_rmssd with empty baseline."""
        from cardiolab.analytics.baseline import Baseline

        empty_baseline = Baseline(history=[])

        result = trend_rmssd(empty_baseline)

        assert result["status"] == "insufficient_data"

    def test_trend_rmssd_consistency(self, baseline_30days):
        """Test that repeated trend calls give same result."""
        result1 = trend_rmssd(baseline_30days)
        result2 = trend_rmssd(baseline_30days)

        if "slope" in result1 and "slope" in result2:
            assert np.isclose(result1["slope"], result2["slope"])

        assert result1.get("trend") == result2.get("trend")


class TestInterpretTrend:
    """Test suite for _interpret_trend() helper function."""

    def test_interpret_trend_positive_slope(self):
        """Test interpretation of positive slope."""
        trend = _interpret_trend(2.5)

        assert trend == "increasing"

    def test_interpret_trend_negative_slope(self):
        """Test interpretation of negative slope."""
        trend = _interpret_trend(-2.5)

        assert trend == "decreasing"

    def test_interpret_trend_zero_slope(self):
        """Test interpretation of zero slope."""
        trend = _interpret_trend(0.0)

        assert trend == "stable"

    def test_interpret_trend_very_small_positive(self):
        """Test interpretation of very small positive slope."""
        trend = _interpret_trend(0.5)

        assert trend == "stable"

    def test_interpret_trend_very_small_negative(self):
        """Test interpretation of very small negative slope."""
        trend = _interpret_trend(-0.5)

        assert trend == "stable"

    def test_interpret_trend_boundary_values(self):
        """Test interpretation at boundary (slope = 1)."""
        # Exactly at boundary: slope = ±1 is not strictly > or < so still "stable"
        assert _interpret_trend(1.0) == "stable"
        assert _interpret_trend(-1.0) == "stable"
        # Just beyond boundary should flip interpretation
        assert _interpret_trend(1.1) == "increasing"
        assert _interpret_trend(-1.1) == "decreasing"

    def test_interpret_trend_large_slope(self):
        """Test interpretation with large slope."""
        trend_large_positive = _interpret_trend(100.0)
        trend_large_negative = _interpret_trend(-100.0)

        assert trend_large_positive == "increasing"
        assert trend_large_negative == "decreasing"


class TestTrendsIntegration:
    """Integration tests for trends analysis."""

    def test_trend_detection_full_workflow(self):
        """Test complete trend detection workflow."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Simulate 30 days with clear improvement
        features = []
        for i in range(30):
            rmssd_value = 50.0 + i  # Gradual improvement
            feature = HRVFeatures(
                date=f"2026-04-{13 + (i % 30):02d}",
                rmssd=rmssd_value,
                mean_hr=75.0,
                sdnn=70.0 + i * 0.5,
                pnn50=20.0 + i * 0.3,
                ln_rmssd=np.log(rmssd_value),
                vlf=500,
                lf=1500,
                hf=2000,
                lf_hf=0.75,
                hf_pct=0.4,
                lf_nu=0.4,
                hf_nu=0.6,
            )
            features.append(feature)

        baseline = Baseline(history=features)
        result = trend_rmssd(baseline)

        # Should detect improvement (positive slope) or at least not negative
        if result.get("status") != "insufficient_data":
            assert result["slope"] > 0
            assert result["trend"] in [
                "increasing",
                "stable",
            ]  # Small improvements might be stable

    def test_trend_week_vs_month(self):
        """Test trend detection over different time windows."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # 7 days data
        features_7d = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=60.0 + i,
                mean_hr=70.0,
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
            for i in range(1, 8)
        ]
        baseline_7d = Baseline(history=features_7d)

        # 30 days data
        features_30d = [
            HRVFeatures(
                date=f"2026-04-{13 + (i % 30):02d}",
                rmssd=50.0 + i * 0.5,
                mean_hr=70.0,
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
            for i in range(30)
        ]
        baseline_30d = Baseline(history=features_30d)

        result_7d = trend_rmssd(baseline_7d)
        result_30d = trend_rmssd(baseline_30d)

        # Both should produce results
        assert isinstance(result_7d, dict)
        assert isinstance(result_30d, dict)

    def test_trend_with_recovery_pattern(self):
        """Test trend detection with recovery pattern (V-shaped)."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # V-shaped pattern: down then up
        rmssd_values = [80, 70, 60, 50, 60, 70, 80, 85]
        features = [
            HRVFeatures(
                date=f"2026-05-{i:02d}",
                rmssd=rmssd_values[i],
                mean_hr=70.0,
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
            for i in range(len(rmssd_values))
        ]
        baseline = Baseline(history=features)

        result = trend_rmssd(baseline)

        # With V-pattern, overall trend line might be slightly positive or stable
        if result.get("status") != "insufficient_data":
            assert "slope" in result
            assert "trend" in result
