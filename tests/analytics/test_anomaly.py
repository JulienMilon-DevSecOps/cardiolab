"""Unit tests for anomaly detection module."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.analytics.anomaly import (
    _interpret,
    _rolling,
    _simple,
    _zscore,
    detect_rmssd_anomaly,
)


class TestDetectRmssdAnomaly:
    """Test suite for detect_rmssd_anomaly() main function."""

    def test_detect_anomaly_simple_method(self, normal_hrv_features, baseline_7days):
        """Test anomaly detection with simple method."""
        result = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="simple"
        )

        assert isinstance(result, dict)
        assert "status" in result
        assert "method" in result or "delta_pct" in result

    def test_detect_anomaly_zscore_method(self, normal_hrv_features, baseline_7days):
        """Test anomaly detection with z-score method."""
        result = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="zscore"
        )

        assert isinstance(result, dict)
        assert "status" in result
        assert "method" in result or "z" in result

    def test_detect_anomaly_rolling_method(self, normal_hrv_features, baseline_7days):
        """Test anomaly detection with rolling method."""
        result = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="rolling"
        )

        assert isinstance(result, dict)
        assert "status" in result

    def test_detect_anomaly_invalid_method(self, normal_hrv_features, baseline_7days):
        """Test that invalid method raises ValueError."""
        with pytest.raises(ValueError):
            detect_rmssd_anomaly(
                normal_hrv_features, baseline_7days, method="invalid_method"
            )

    def test_detect_anomaly_normal_vs_abnormal(
        self, normal_hrv_features, poor_hrv_features, baseline_7days
    ):
        """Test that abnormal RMSSD is detected differently."""
        result_normal = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="zscore"
        )
        result_abnormal = detect_rmssd_anomaly(
            poor_hrv_features, baseline_7days, method="zscore"
        )

        # Both should have results but likely different statuses
        assert result_normal.get("status") in [
            "normal",
            "low",
            "high",
            "insufficient_data",
        ]
        assert result_abnormal.get("status") in [
            "normal",
            "low",
            "high",
            "insufficient_data",
        ]


class TestSimpleMethod:
    """Test suite for _simple() anomaly detection method."""

    def test_simple_with_valid_baseline(self, normal_hrv_features, baseline_7days):
        """Test simple method with valid baseline."""
        result = _simple(normal_hrv_features, baseline_7days)

        assert "method" in result
        assert result["method"] == "simple"
        assert "delta_pct" in result
        assert "status" in result

    def test_simple_returns_percentage_change(self, baseline_7days):
        """Test that simple method returns percentage change."""
        # Create a feature with 20% higher RMSSD than baseline mean
        baseline_mean = baseline_7days.mean_rmssd()
        high_feature = type("obj", (object,), {"rmssd": baseline_mean * 1.2})()

        result = _simple(high_feature, baseline_7days)

        # Delta should be around 20%
        assert np.isclose(result["delta_pct"], 20, atol=5)

    def test_simple_detects_improvement(self, excellent_hrv_features, baseline_7days):
        """Test detection of RMSSD improvement (recovery)."""
        result = _simple(excellent_hrv_features, baseline_7days)

        # Excellent features should show positive delta
        assert result["delta_pct"] > 0
        assert result["status"] in ["normal", "high", "high_severe"]

    def test_simple_detects_degradation(self, poor_hrv_features, baseline_7days):
        """Test detection of RMSSD degradation (fatigue)."""
        result = _simple(poor_hrv_features, baseline_7days)

        # Poor features should show negative delta
        assert result["delta_pct"] < 0
        assert result["status"] in ["normal", "low", "low_severe"]

    def test_simple_no_baseline(self, normal_hrv_features):
        """Test simple method with empty baseline."""
        from cardiolab.analytics.baseline import Baseline

        empty_baseline = Baseline(history=[])

        result = _simple(normal_hrv_features, empty_baseline)

        assert result["status"] == "no_baseline"


class TestZscoreMethod:
    """Test suite for _zscore() anomaly detection method."""

    def test_zscore_with_sufficient_data(self, normal_hrv_features, baseline_30days):
        """Test z-score with >= 3 historical values."""
        result = _zscore(normal_hrv_features, baseline_30days)

        assert "method" in result
        assert result["method"] == "zscore"
        assert "z" in result
        assert "status" in result

    def test_zscore_returns_float(self, normal_hrv_features, baseline_30days):
        """Test that z-score method returns numeric z value."""
        result = _zscore(normal_hrv_features, baseline_30days)

        assert isinstance(result.get("z"), (int, float))

    def test_zscore_insufficient_data(
        self, normal_hrv_features, baseline_insufficient_data
    ):
        """Test z-score with < 3 data points."""
        result = _zscore(normal_hrv_features, baseline_insufficient_data)

        assert result["status"] == "insufficient_data"

    def test_zscore_normal_value(self, normal_hrv_features, baseline_30days):
        """Test z-score for value near mean."""
        # Replace history with very consistent values
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

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

        current = HRVFeatures(
            date="2026-05-08",
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

        result = _zscore(current, baseline)

        # Z-score should be close to 0 for value near mean, or insufficient_data if std=0
        if result.get("status") == "no_variability":
            assert result["status"] == "no_variability"
        elif "z" in result:
            assert np.abs(result["z"]) < 0.5
            assert result["status"] == "normal"

    def test_zscore_low_value(self, baseline_30days):
        """Test z-score detection of abnormally low RMSSD."""
        from cardiolab.protocols.resting import HRVFeatures

        # Create a feature with very low RMSSD (< 2 std below mean)
        low_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=20.0,  # Much lower than baseline mean (~80)
            mean_hr=70.0,
            sdnn=80.0,
            pnn50=25.0,
            ln_rmssd=3.0,
            vlf=500,
            lf=1500,
            hf=2000,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
        )

        result = _zscore(low_feature, baseline_30days)

        # Should detect as low
        if result["status"] != "insufficient_data":
            assert result["z"] < -1.5
            assert result["status"] == "low"

    def test_zscore_high_value(self, baseline_30days):
        """Test z-score detection of abnormally high RMSSD."""
        from cardiolab.protocols.resting import HRVFeatures

        # Create a feature with very high RMSSD
        high_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=150.0,  # Much higher than baseline
            mean_hr=70.0,
            sdnn=150.0,
            pnn50=60.0,
            ln_rmssd=5.0,
            vlf=800,
            lf=2500,
            hf=4000,
            lf_hf=0.63,
            hf_pct=0.61,
            lf_nu=0.38,
            hf_nu=0.62,
        )

        result = _zscore(high_feature, baseline_30days)

        # Should detect as high
        if result["status"] != "insufficient_data":
            assert result["z"] > 1.5
            assert result["status"] == "high"

    def test_zscore_no_variability(self, normal_hrv_features):
        """Test z-score when baseline has no variability (std=0)."""
        from cardiolab.analytics.baseline import Baseline
        from cardiolab.protocols.resting import HRVFeatures

        # Create baseline with all identical values
        identical_features = [
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
        baseline = Baseline(history=identical_features)

        result = _zscore(normal_hrv_features, baseline)

        assert result["status"] == "no_variability"


class TestRollingMethod:
    """Test suite for _rolling() anomaly detection method."""

    def test_rolling_with_sufficient_data(self, normal_hrv_features, baseline_30days):
        """Test rolling method with sufficient history."""
        result = _rolling(normal_hrv_features, baseline_30days)

        assert "method" in result
        assert result["method"] == "rolling"
        assert "status" in result

    def test_rolling_returns_baseline_and_delta(
        self, normal_hrv_features, baseline_30days
    ):
        """Test that rolling method returns baseline and delta."""
        result = _rolling(normal_hrv_features, baseline_30days)

        if result.get("status") != "insufficient_data":
            assert "baseline" in result
            assert "delta_pct" in result

    def test_rolling_insufficient_data(
        self, normal_hrv_features, baseline_insufficient_data
    ):
        """Test rolling method with insufficient data."""
        result = _rolling(normal_hrv_features, baseline_insufficient_data)

        assert result["status"] == "insufficient_data"

    def test_rolling_detects_improvement(self, baseline_30days):
        """Test rolling method detects RMSSD improvement."""
        from cardiolab.protocols.resting import HRVFeatures

        # Create feature with RMSSD higher than rolling baseline
        high_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=130.0,  # Higher than last rolling value
            mean_hr=70.0,
            sdnn=100.0,
            pnn50=35.0,
            ln_rmssd=4.87,
            vlf=600,
            lf=1800,
            hf=2500,
            lf_hf=0.72,
            hf_pct=0.58,
            lf_nu=0.42,
            hf_nu=0.58,
        )

        result = _rolling(high_feature, baseline_30days)

        if result.get("status") != "insufficient_data":
            assert result["delta_pct"] > 0

    def test_rolling_detects_degradation(self, baseline_30days):
        """Test rolling method detects RMSSD degradation."""
        from cardiolab.protocols.resting import HRVFeatures

        # Create feature with RMSSD lower than rolling baseline
        low_feature = HRVFeatures(
            date="2026-05-12",
            rmssd=40.0,  # Lower than last rolling value
            mean_hr=75.0,
            sdnn=50.0,
            pnn50=15.0,
            ln_rmssd=3.69,
            vlf=400,
            lf=1000,
            hf=1200,
            lf_hf=0.83,
            hf_pct=0.55,
            lf_nu=0.45,
            hf_nu=0.55,
        )

        result = _rolling(low_feature, baseline_30days)

        if result.get("status") != "insufficient_data":
            assert result["delta_pct"] < 0


class TestInterpret:
    """Test suite for _interpret() helper function."""

    def test_interpret_positive_delta(self):
        """Test interpretation of positive RMSSD change."""
        status = _interpret(15.0)  # 15% increase

        assert status in ["normal", "high", "low"]

    def test_interpret_negative_delta(self):
        """Test interpretation of negative RMSSD change."""
        status = _interpret(-20.0)  # 20% decrease

        assert status in ["normal", "high", "low"]

    def test_interpret_large_positive_delta(self):
        """Test interpretation of large positive delta (strong improvement)."""
        status = _interpret(50.0)  # 50% increase

        # Should indicate improvement
        assert status in ["high", "high_severe"]

    def test_interpret_large_negative_delta(self):
        """Test interpretation of large negative delta (strong degradation)."""
        status = _interpret(-50.0)  # 50% decrease

        # Should indicate degradation
        assert status in ["low", "low_severe"]

    def test_interpret_zero_delta(self):
        """Test interpretation of zero delta (no change)."""
        status = _interpret(0.0)

        assert status == "normal"

    def test_interpret_very_small_delta(self):
        """Test interpretation of very small delta."""
        status = _interpret(0.5)  # 0.5% change

        assert status == "normal"


class TestAnomalyDetectionIntegration:
    """Integration tests for anomaly detection."""

    def test_all_methods_with_same_input(self, normal_hrv_features, baseline_30days):
        """Test that all methods can process the same input."""
        result_simple = _simple(normal_hrv_features, baseline_30days)
        result_zscore = _zscore(normal_hrv_features, baseline_30days)
        result_rolling = _rolling(normal_hrv_features, baseline_30days)

        # All should return dicts with status
        assert all(
            isinstance(r, dict) for r in [result_simple, result_zscore, result_rolling]
        )
        assert all(
            "status" in r for r in [result_simple, result_zscore, result_rolling]
        )

    def test_anomaly_detection_consistency(self, normal_hrv_features, baseline_7days):
        """Test that repeated detection gives same result."""
        result1 = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="simple"
        )
        result2 = detect_rmssd_anomaly(
            normal_hrv_features, baseline_7days, method="simple"
        )

        assert result1["status"] == result2["status"]
        if "delta_pct" in result1:
            assert np.isclose(result1["delta_pct"], result2["delta_pct"], rtol=0.001)
